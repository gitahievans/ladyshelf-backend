import logging

from notifications.email_templates import (
    BRAND_CONTEXT,
    build_order_context,
    get_customer_email,
    get_staff_emails,
    send_templated_email,
)
from orders.models import Order

logger = logging.getLogger(__name__)


def send_order_created_notifications(order: Order) -> None:
    customer_email = get_customer_email(order)
    staff_emails = get_staff_emails()

    if customer_email:
        send_templated_email(
            subject=f"Wahi Fashion order received: {order.order_number}",
            template_name="order_customer",
            context=build_order_context(
                order,
                headline="Order received.",
                intro=(
                    f"your Wahi Fashion order {order.order_number} has been received. "
                    "We will prepare it with care and keep you updated."
                ),
            ),
            recipients=[customer_email],
        )

    if staff_emails:
        send_templated_email(
            subject=f"New order placed: {order.order_number}",
            template_name="order_staff",
            context=build_order_context(
                order,
                headline="New order placed.",
                intro="A new Wahi Fashion order has been created and needs store review.",
            ),
            recipients=staff_emails,
        )

    # TODO: Add Africa's Talking SMS dispatch for customer and staff notifications.
    logger.info("Order notifications queued for email only for order %s", order.order_number)


def send_order_paid_notifications(order: Order) -> None:
    customer_email = get_customer_email(order)
    staff_emails = get_staff_emails()

    if customer_email:
        send_templated_email(
            subject=f"Payment confirmed: {order.order_number}",
            template_name="order_customer",
            context=build_order_context(
                order,
                headline="Payment confirmed.",
                intro=(
                    f"payment for your Wahi Fashion order {order.order_number} has been "
                    "confirmed. Your order is now with the store team."
                ),
            ),
            recipients=[customer_email],
        )

    if staff_emails:
        send_templated_email(
            subject=f"Paid order ready for action: {order.order_number}",
            template_name="order_staff",
            context=build_order_context(
                order,
                headline="Paid order ready for action.",
                intro="Payment has been confirmed. Please prepare the next fulfillment step.",
            ),
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

    if order.payment_status != Order.PaymentStatus.FAILED:
        return

    customer_email = get_customer_email(order)
    if not customer_email:
        return

    send_templated_email(
        subject=f"Payment needs attention: {order.order_number}",
        template_name="payment_failed",
        context=build_order_context(
            order,
            headline="Your order is still reserved.",
            intro="We could not confirm payment for your order.",
        ),
        recipients=[customer_email],
    )
    logger.info("Payment status email sent for order %s", order.order_number)


def send_account_created_notification(*, email: str, customer_name: str) -> None:
    send_templated_email(
        subject="Welcome to Wahi Fashion",
        template_name="account_created",
        context={
            **BRAND_CONTEXT,
            "customer_name": customer_name,
        },
        recipients=[email],
    )
