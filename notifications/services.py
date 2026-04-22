import logging

from django.conf import settings
from django.core.mail import send_mail

from orders.models import Order

logger = logging.getLogger(__name__)


def _format_order_total(order: Order) -> str:
    if order.manual_delivery_fee_confirmation_required:
        return f"KES {order.subtotal:,} + delivery confirmation"

    return f"KES {order.total:,}"


def _format_line_items(order: Order) -> str:
    return "\n".join(
        [
            f"- {item.product_name} ({item.size} / {item.color}) x{item.quantity}"
            for item in order.items.all()
        ]
    )


def _build_customer_message(order: Order) -> str:
    delivery_name = order.delivery_details.get("fullName", "there")
    lines = [
        f"Hello {delivery_name},",
        "",
        f"Your Wahi Fashion order {order.order_number} has been received.",
        f"Current order status: {order.order_status.replace('_', ' ').title()}",
        f"Payment status: {order.payment_status.replace('_', ' ').title()}",
        f"Order total: {_format_order_total(order)}",
        "",
        "Items:",
        _format_line_items(order),
    ]

    if order.delivery_mode == Order.DeliveryMode.PICKUP and order.pickup_instructions:
        lines.extend(
            [
                "",
                "Pickup details:",
                f"{order.pickup_instructions.get('streetAddress', '')}",
                (
                    f"{order.pickup_instructions.get('town', '')}, "
                    f"{order.pickup_instructions.get('county', '')}"
                ),
            ]
        )

    if order.delivery_mode == Order.DeliveryMode.PARCEL and order.payment_status == Order.PaymentStatus.PAID:
        lines.extend(
            [
                "",
                "A store attendant will contact you to arrange parcel dispatch.",
            ]
        )

    lines.extend(
        [
            "",
            "Thank you for shopping with Wahi Fashion.",
        ]
    )

    return "\n".join(lines)


def _build_staff_message(order: Order) -> str:
    customer_email = order.customer.email if order.customer else order.guest_email
    delivery_details = order.delivery_details
    return "\n".join(
        [
            "A new Wahi Fashion order has been created.",
            "",
            f"Order number: {order.order_number}",
            f"Customer email: {customer_email}",
            f"Phone: {delivery_details.get('phone', '')}",
            f"Delivery mode: {order.delivery_mode}",
            f"Order status: {order.order_status}",
            f"Payment status: {order.payment_status}",
            f"Total: {_format_order_total(order)}",
            "",
            "Items:",
            _format_line_items(order),
        ]
    )


def _send_email(subject: str, message: str, recipients: list[str]) -> None:
    if not recipients:
        return

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=False,
    )


def _get_customer_email(order: Order) -> str:
    return order.customer.email if order.customer else order.guest_email


def _get_staff_emails() -> list[str]:
    return list(getattr(settings, "ORDER_NOTIFICATION_STAFF_EMAILS", []))


def send_order_created_notifications(order: Order) -> None:
    customer_email = _get_customer_email(order)
    staff_emails = _get_staff_emails()

    if customer_email:
        _send_email(
            subject=f"Wahi Fashion order received: {order.order_number}",
            message=_build_customer_message(order),
            recipients=[customer_email],
        )

    if staff_emails:
        _send_email(
            subject=f"New order placed: {order.order_number}",
            message=_build_staff_message(order),
            recipients=staff_emails,
        )

    # TODO: Add Africa's Talking SMS dispatch for customer and staff notifications.
    logger.info("Order notifications queued for email only for order %s", order.order_number)


def send_order_paid_notifications(order: Order) -> None:
    customer_email = _get_customer_email(order)
    staff_emails = _get_staff_emails()

    if customer_email:
        _send_email(
            subject=f"Payment confirmed: {order.order_number}",
            message=_build_customer_message(order),
            recipients=[customer_email],
        )

    if staff_emails:
        _send_email(
            subject=f"Paid order ready for action: {order.order_number}",
            message=_build_staff_message(order),
            recipients=staff_emails,
        )

    logger.info("Paid-order notifications queued for email only for order %s", order.order_number)


def send_payment_status_notification(order_id: int) -> None:
    try:
        order = (
            Order.objects.select_related("customer")
            .prefetch_related("items", "items__product")
            .get(pk=order_id)
        )
    except Order.DoesNotExist:
        logger.warning("Payment notification skipped because order %s no longer exists", order_id)
        return

    if order.payment_status == Order.PaymentStatus.PAID:
        send_order_paid_notifications(order)
        logger.info("Payment status email sent for order %s", order.order_number)
        return
    elif order.payment_status == Order.PaymentStatus.FAILED:
        customer_email = _get_customer_email(order)
        if not customer_email:
            return

        subject = f"Payment needs attention: {order.order_number}"
        body = "\n".join(
            [
                f"Hello {order.delivery_details.get('fullName', 'there')},",
                "",
                (
                    f"We could not confirm payment for your Wahi Fashion order "
                    f"{order.order_number}."
                ),
                "You can return to checkout and try the payment again.",
                f"Current order status: {order.order_status.replace('_', ' ').title()}",
                "",
                "If you need help, reply to this email and our team will assist.",
            ]
        )
    else:
        return

    _send_email(subject=subject, message=body, recipients=[customer_email])
    logger.info("Payment status email sent for order %s", order.order_number)
