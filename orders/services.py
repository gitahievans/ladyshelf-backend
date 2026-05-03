import logging
import secrets

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from catalog.models import Product, ProductVariant
from checkout.serializers import PickupLocationSerializer
from checkout.services import (
    build_payment_options,
    build_validated_cart_items,
    get_active_pickup_location,
    resolve_delivery_quote_context,
    validate_payment_selection,
)
from customers.models import CustomerProfile
from notifications.services import (
    send_order_cancellation_notifications,
    send_order_created_notifications,
)
from orders.expiry import get_payment_expiry_deadline
from orders.models import Order, OrderCancellation, OrderCancellationItem, OrderItem

logger = logging.getLogger(__name__)


def get_order_cancellation_unavailable_reason(order: Order) -> str:
    if order.payment_timing != Order.PaymentTiming.PAY_ON_DELIVERY:
        return "Only pay-on-delivery orders can be cancelled online."

    if order.order_status != Order.OrderStatus.NEW:
        return "This order is already being prepared or has moved to dispatch."

    if not any(item.quantity > item.cancelled_quantity for item in order.items.all()):
        return "Every item in this order has already been cancelled."

    return ""


def can_cancel_order(order: Order) -> bool:
    return get_order_cancellation_unavailable_reason(order) == ""


def build_checkout_quote_data(
    *,
    cart_lines: list[dict],
    delivery_details: dict,
    payment_selection: dict | None = None,
    lock_variants: bool = False,
) -> dict:
    validated_items, subtotal = build_validated_cart_items(
        cart_lines,
        lock_variants=lock_variants,
    )
    delivery_method = delivery_details["deliveryMethod"]
    messages: list[str] = []
    pickup_instructions = None

    if delivery_method == "pickup":
        pickup_location = get_active_pickup_location()
        delivery_mode = Order.DeliveryMode.PICKUP
        delivery_fee = 0
        manual_fee_confirmation_required = False
        estimated_window = (
            f"Collect within {pickup_location.collection_window_hours} hours after confirmation."
        )
        available_options = build_payment_options(
            delivery_mode=delivery_mode,
            allow_pay_on_delivery=False,
        )
        pickup_instructions = PickupLocationSerializer(pickup_location).data
        messages.append("Pickup is prepaid only.")
    else:
        delivery_context = resolve_delivery_quote_context(
            delivery_details=delivery_details,
        )
        delivery_mode = delivery_context["deliveryMode"]
        delivery_fee = delivery_context["deliveryFee"]
        manual_fee_confirmation_required = delivery_context[
            "manualDeliveryFeeConfirmationRequired"
        ]
        estimated_window = delivery_context["estimatedWindow"]
        available_options = build_payment_options(
            delivery_mode=delivery_mode,
            allow_pay_on_delivery=delivery_context["allowPayOnDelivery"],
        )

        if delivery_mode == Order.DeliveryMode.PARCEL:
            messages.append("Parcel delivery is prepaid only.")

        if delivery_mode == Order.DeliveryMode.PARCEL:
            messages.append(
                "Parcel orders are prepaid. A store attendant will contact you after payment to arrange dispatch."
            )
        else:
            messages.append(
                "Rider delivery is priced automatically from straight-line distance to the shop."
            )

    resolved_payment_selection = validate_payment_selection(
        payment_selection=payment_selection,
        available_options=available_options,
    )
    total = subtotal + delivery_fee

    return {
        "currency": "KES",
        "items": validated_items,
        "subtotal": subtotal,
        "deliveryFee": delivery_fee,
        "total": total,
        "fulfillmentMethod": delivery_method,
        "deliveryMode": delivery_mode,
        "estimatedWindow": estimated_window,
        "manualDeliveryFeeConfirmationRequired": manual_fee_confirmation_required,
        "availablePaymentOptions": available_options,
        "paymentSelection": resolved_payment_selection,
        "messages": messages,
        "pickupInstructions": pickup_instructions,
        "distanceKm": delivery_context["distanceKm"] if delivery_method != "pickup" else None,
        "deliveryRuleLabel": delivery_context["ruleLabel"] if delivery_method != "pickup" else "",
    }


def generate_order_number() -> str:
    current_year = timezone.localdate().year

    for _ in range(20):
        suffix = secrets.randbelow(90000) + 10000
        order_number = f"WF-{current_year}-{suffix}"

        if not Order.objects.filter(order_number=order_number).exists():
            return order_number

    raise ValidationError({"detail": "We could not create an order number. Please try again."})


def resolve_initial_order_state(quote_data: dict, payment_selection: dict) -> dict[str, str | bool]:
    if payment_selection["timing"] == Order.PaymentTiming.PAY_ON_DELIVERY:
        return {
            "payment_method": payment_selection["method"],
            "payment_timing": payment_selection["timing"],
            "payment_status": Order.PaymentStatus.MANUAL_ON_DELIVERY,
            "order_status": Order.OrderStatus.NEW,
        }

    return {
        "payment_method": payment_selection["method"],
        "payment_timing": payment_selection["timing"],
        "payment_status": Order.PaymentStatus.PENDING,
        "order_status": Order.OrderStatus.AWAITING_PAYMENT,
    }


@transaction.atomic
def create_order_from_checkout(
    *,
    cart_lines: list[dict],
    delivery_details: dict,
    payment_selection: dict,
    customer: CustomerProfile | None = None,
) -> Order:
    quote_data = build_checkout_quote_data(
        cart_lines=cart_lines,
        delivery_details=delivery_details,
        payment_selection=payment_selection,
        lock_variants=True,
    )
    order_state = resolve_initial_order_state(quote_data, payment_selection)

    order = Order.objects.create(
        customer=customer,
        guest_email="" if customer else delivery_details["email"],
        order_number=generate_order_number(),
        delivery_details=delivery_details,
        subtotal=quote_data["subtotal"],
        delivery_fee=quote_data["deliveryFee"],
        discount=0,
        total=quote_data["total"],
        currency=quote_data["currency"],
        delivery_mode=quote_data["deliveryMode"],
        payment_method=order_state["payment_method"],
        payment_timing=order_state["payment_timing"],
        payment_status=order_state["payment_status"],
        order_status=order_state["order_status"],
        manual_delivery_fee_confirmation_required=quote_data[
            "manualDeliveryFeeConfirmationRequired"
        ],
        payment_expires_at=(
            get_payment_expiry_deadline()
            if payment_selection["timing"] == Order.PaymentTiming.PREPAY
            else None
        ),
        pickup_instructions=quote_data["pickupInstructions"],
    )

    variant_quantities: dict[str, int] = {}

    for item in quote_data["items"]:
        variant_quantities[item["variantId"]] = item["quantity"]
        product = Product.objects.filter(external_id=item["productId"]).first()
        OrderItem.objects.create(
            order=order,
            product=product,
            variant_id=item["variantId"],
            quantity=item["quantity"],
            product_name=item["productName"],
            product_image=item["productImage"],
            price=item["price"],
            currency=item["currency"],
            size=item["size"],
            color=item["color"],
            color_hex=item["colorHex"],
        )

    for item in quote_data["items"]:
        quantity = variant_quantities[item["variantId"]]
        variant = ProductVariant.objects.select_for_update().get(external_id=item["variantId"])
        if variant.stock < quantity:
            raise ValidationError(
                {
                    "detail": (
                        f"Only {variant.stock} piece(s) remain for "
                        f"{variant.product.name} in {variant.color} / {variant.size}."
                    )
                }
            )
        variant.stock -= quantity
        variant.save(update_fields=["stock", "updated_at"])

    transaction.on_commit(lambda: _send_notifications_safely(order.pk))

    return order


def _send_notifications_safely(order_id: int) -> None:
    try:
        order = (
            Order.objects.select_related("customer")
            .prefetch_related("items", "items__product")
            .get(pk=order_id)
        )
        if order.payment_timing != Order.PaymentTiming.PAY_ON_DELIVERY:
            logger.info(
                "Skipping immediate notifications for prepaid order %s until payment confirmation",
                order.order_number,
            )
            return
        send_order_created_notifications(order)
    except Exception:  # pragma: no cover - notification failures should not break checkout
        logger.exception("Failed to send order notifications for order %s", order_id)


@transaction.atomic
def cancel_order_items(
    *,
    order: Order,
    customer: CustomerProfile,
    cancellation_items: list[dict],
    reason: str,
    note: str = "",
) -> Order:
    locked_order = (
        Order.objects.select_for_update()
        .select_related("customer")
        .prefetch_related("items", "items__product")
        .get(pk=order.pk, customer=customer)
    )
    unavailable_reason = get_order_cancellation_unavailable_reason(locked_order)
    if unavailable_reason:
        raise ValidationError({"detail": unavailable_reason})

    quantity_by_item_id: dict[int, int] = {}
    for cancellation_item in cancellation_items:
        order_item_id = int(cancellation_item["orderItemId"])
        quantity = int(cancellation_item["quantity"])
        quantity_by_item_id[order_item_id] = quantity_by_item_id.get(order_item_id, 0) + quantity

    locked_items = {
        item.pk: item
        for item in OrderItem.objects.select_for_update().filter(
            order=locked_order,
            pk__in=quantity_by_item_id.keys(),
        )
    }
    if len(locked_items) != len(quantity_by_item_id):
        raise ValidationError({"items": "One or more selected order items could not be found."})

    cancellation = OrderCancellation.objects.create(
        order=locked_order,
        customer=customer,
        source=OrderCancellation.Source.CUSTOMER,
        reason=reason,
        note=note.strip(),
    )

    for order_item_id, quantity in quantity_by_item_id.items():
        if quantity < 1:
            raise ValidationError({"items": "Cancellation quantity must be at least 1."})

        order_item = locked_items[order_item_id]
        remaining_quantity = order_item.quantity - order_item.cancelled_quantity
        if quantity > remaining_quantity:
            raise ValidationError(
                {
                    "items": (
                        f"Only {remaining_quantity} piece(s) can still be cancelled "
                        f"for {order_item.product_name}."
                    )
                }
            )

        order_item.cancelled_quantity += quantity
        order_item.save(update_fields=["cancelled_quantity", "updated_at"])
        OrderCancellationItem.objects.create(
            cancellation=cancellation,
            order_item=order_item,
            quantity=quantity,
            unit_price=order_item.price,
            line_total=order_item.price * quantity,
        )

        variant = ProductVariant.objects.select_for_update().filter(
            external_id=order_item.variant_id,
        ).first()
        if variant:
            variant.stock += quantity
            variant.save(update_fields=["stock", "updated_at"])

    locked_order.refresh_from_db()
    current_items = OrderItem.objects.filter(order=locked_order)
    active_subtotal = sum(
        item.price * max(item.quantity - item.cancelled_quantity, 0)
        for item in current_items
    )
    all_items_cancelled = active_subtotal == 0
    locked_order.subtotal = active_subtotal
    locked_order.delivery_fee = 0 if all_items_cancelled else locked_order.delivery_fee
    locked_order.total = max(0, locked_order.subtotal + locked_order.delivery_fee - locked_order.discount)
    if all_items_cancelled:
        locked_order.order_status = Order.OrderStatus.CANCELLED

    locked_order.save(
        update_fields=[
            "subtotal",
            "delivery_fee",
            "total",
            "order_status",
            "updated_at",
        ]
    )
    transaction.on_commit(lambda: send_order_cancellation_notifications(cancellation.pk))

    return (
        Order.objects.select_related("customer")
        .prefetch_related("items", "items__product", "cancellations", "cancellations__items", "cancellations__items__order_item")
        .get(pk=locked_order.pk)
    )
