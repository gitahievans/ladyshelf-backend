import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from notifications.email_templates import (
    build_order_context,
    get_customer_email,
    send_templated_email,
)
from orders.models import Order
from payments.models import PaymentTransaction, Receipt

logger = logging.getLogger(__name__)


def build_receipt_number(order: Order) -> str:
    return f"WAHI-RCPT-{timezone.now().year}-{order.pk:06d}"


def get_payment_reference(
    *,
    order: Order,
    payment_reference: str = "",
    payment_transaction: PaymentTransaction | None = None,
) -> str:
    reference = payment_reference.strip()
    if reference:
        return reference

    if payment_transaction:
        return (
            payment_transaction.transaction_code
            or payment_transaction.checkout_request_id
            or payment_transaction.merchant_reference
        )

    return order.order_number


def get_receipt_context(receipt: Receipt) -> dict:
    context = build_order_context(
        receipt.order,
        headline="Your Wahi Fashion receipt.",
        intro=(
            "thank you for your payment. Your receipt is ready, and your order "
            "is now being handled with care by our store team."
        ),
    )
    context.update(
        {
            "receipt": receipt,
            "receipt_number": receipt.receipt_number,
            "issued_at": receipt.issued_at,
            "payment_reference": receipt.payment_reference,
            "total_paid_label": f"{receipt.currency} {receipt.total_paid:,}",
        }
    )
    return context


def send_receipt_email(receipt: Receipt) -> Receipt:
    customer_email = get_customer_email(receipt.order)
    if not customer_email:
        receipt.status = Receipt.Status.FAILED
        receipt.save(update_fields=["status", "updated_at"])
        logger.warning("Receipt email skipped because order %s has no customer email", receipt.order.order_number)
        return receipt

    try:
        send_templated_email(
            subject=f"Your Wahi Fashion receipt: {receipt.receipt_number}",
            template_name="receipt_customer",
            context=get_receipt_context(receipt),
            recipients=[customer_email],
        )
    except Exception:
        receipt.status = Receipt.Status.FAILED
        receipt.save(update_fields=["status", "updated_at"])
        raise

    receipt.status = Receipt.Status.SENT
    receipt.sent_at = timezone.now()
    receipt.sent_to_email = customer_email
    receipt.save(update_fields=["status", "sent_at", "sent_to_email", "updated_at"])
    logger.info("Receipt %s emailed for order %s", receipt.receipt_number, receipt.order.order_number)
    return receipt


@transaction.atomic
def issue_receipt_for_paid_order(
    *,
    order: Order,
    payment_transaction: PaymentTransaction | None = None,
    payment_reference: str = "",
    total_paid: int | None = None,
    created_by=None,
    send_email: bool = True,
) -> Receipt:
    if order.payment_status != Order.PaymentStatus.PAID:
        raise ValidationError({"detail": "Receipts can only be issued after payment is confirmed."})

    try:
        existing_receipt = order.receipt
    except Receipt.DoesNotExist:
        existing_receipt = None

    if existing_receipt:
        if send_email and existing_receipt.status != Receipt.Status.SENT:
            transaction.on_commit(lambda: send_receipt_email(existing_receipt))
        return existing_receipt

    receipt = Receipt.objects.create(
        order=order,
        payment_transaction=payment_transaction,
        receipt_number=build_receipt_number(order),
        total_paid=total_paid if total_paid is not None else order.total,
        currency=order.currency,
        payment_method=order.payment_method,
        payment_reference=get_payment_reference(
            order=order,
            payment_reference=payment_reference,
            payment_transaction=payment_transaction,
        ),
        created_by=created_by,
        metadata={
            "deliveryMode": order.delivery_mode,
            "paymentTiming": order.payment_timing,
        },
    )

    if send_email:
        transaction.on_commit(lambda: send_receipt_email(receipt))

    return receipt


def resend_receipt_for_order(order: Order) -> Receipt:
    try:
        receipt = order.receipt
    except Receipt.DoesNotExist as exc:
        raise ValidationError({"detail": "This order does not have a receipt yet."}) from exc

    return send_receipt_email(receipt)
