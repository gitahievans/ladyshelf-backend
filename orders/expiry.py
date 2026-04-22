import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from catalog.models import ProductVariant
from orders.models import Order
from payments.models import PaymentTransaction

logger = logging.getLogger(__name__)


def get_payment_expiry_deadline() -> timezone.datetime:
    return timezone.now() + timedelta(minutes=settings.PREPAID_ORDER_EXPIRY_MINUTES)


def _append_internal_note(order: Order, message: str) -> None:
    timestamp = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S %Z")
    next_note = f"[{timestamp}] {message}"
    if order.internal_notes.strip():
        order.internal_notes = f"{order.internal_notes.rstrip()}\n{next_note}"
    else:
        order.internal_notes = next_note


def expire_unpaid_prepay_orders(*, now=None) -> int:
    current_time = now or timezone.now()
    expired_order_ids = list(
        Order.objects.filter(
            payment_timing=Order.PaymentTiming.PREPAY,
            payment_status=Order.PaymentStatus.PENDING,
            order_status=Order.OrderStatus.AWAITING_PAYMENT,
            payment_expires_at__isnull=False,
            payment_expires_at__lte=current_time,
        ).values_list("id", flat=True)
    )

    expired_count = 0
    for order_id in expired_order_ids:
        with transaction.atomic():
            order = (
                Order.objects.select_for_update()
                .prefetch_related("items", "payment_transactions")
                .get(pk=order_id)
            )

            if (
                order.payment_timing != Order.PaymentTiming.PREPAY
                or order.payment_status != Order.PaymentStatus.PENDING
                or order.order_status != Order.OrderStatus.AWAITING_PAYMENT
                or not order.payment_expires_at
                or order.payment_expires_at > current_time
            ):
                continue

            variant_ids = [item.variant_id for item in order.items.all()]
            variants = {
                variant.external_id: variant
                for variant in ProductVariant.objects.select_for_update().filter(
                    external_id__in=variant_ids
                )
            }

            for item in order.items.all():
                variant = variants.get(item.variant_id)
                if variant is None:
                    continue
                variant.stock += item.quantity
                variant.save(update_fields=["stock", "updated_at"])

            order.payment_status = Order.PaymentStatus.FAILED
            order.order_status = Order.OrderStatus.CANCELLED
            _append_internal_note(
                order,
                "Auto-cancelled after 30 minutes without prepaid payment confirmation.",
            )
            order.save(
                update_fields=[
                    "payment_status",
                    "order_status",
                    "internal_notes",
                    "updated_at",
                ]
            )

            order.payment_transactions.filter(
                status__in=[
                    PaymentTransaction.Status.INITIATED,
                    PaymentTransaction.Status.PENDING,
                ]
            ).update(
                status=PaymentTransaction.Status.FAILED,
                failed_at=current_time,
                updated_at=current_time,
            )

            expired_count += 1
            logger.info("Expired unpaid prepaid order %s", order.order_number)

    return expired_count
