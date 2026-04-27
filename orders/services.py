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
from notifications.services import send_order_created_notifications
from orders.expiry import get_payment_expiry_deadline
from orders.models import Order, OrderItem

logger = logging.getLogger(__name__)


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
