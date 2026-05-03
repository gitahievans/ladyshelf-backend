from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from orders.models import Order, OrderCancellation


@dataclass(frozen=True)
class TemplatedEmail:
    subject: str
    text_body: str
    html_body: str


BRAND_CONTEXT = {
    "brand_name": "Wahi Fashion",
    "brand_tagline": "More than fashion. A lifestyle.",
    "logo_url": (
        "https://nehcexpdaoypguejwnvg.supabase.co/storage/v1/object/public/"
        "product-images/White%20Logo.png"
    ),
    "website_url": "https://wahifashion.africa",
    "support_email": "orders@wahifashion.com",
    "store_location": "Lumumba Drive, Roysambu, Nairobi",
    "store_hours": "Mon-Sat 9am-7pm, Sun 11am-5pm",
}


def format_money(value: int, currency: str = "KES") -> str:
    return f"{currency} {value:,}"


def format_status(value: str) -> str:
    return value.replace("_", " ").title()


def get_order_total_label(order: Order) -> str:
    if order.manual_delivery_fee_confirmation_required:
        return f"{format_money(order.subtotal, order.currency)} + delivery confirmation"

    return format_money(order.total, order.currency)


def get_customer_email(order: Order) -> str:
    return order.customer.email if order.customer else order.guest_email


def get_staff_emails() -> list[str]:
    return list(getattr(settings, "ORDER_NOTIFICATION_STAFF_EMAILS", []))


def build_order_context(order: Order, *, headline: str, intro: str) -> dict:
    items = [
        {
            "name": item.product_name,
            "image": item.product_image,
            "quantity": item.quantity,
            "size": item.size,
            "color": item.color,
            "price": format_money(item.price, item.currency),
            "line_total": format_money(item.price * item.quantity, item.currency),
        }
        for item in order.items.all()
    ]
    delivery_details = order.delivery_details
    pickup_instructions = order.pickup_instructions or {}

    return {
        **BRAND_CONTEXT,
        "headline": headline,
        "intro": intro,
        "order": order,
        "items": items,
        "customer_name": delivery_details.get("fullName", "there"),
        "customer_email": get_customer_email(order),
        "customer_phone": delivery_details.get("phone", ""),
        "delivery_details": delivery_details,
        "pickup_instructions": pickup_instructions,
        "order_status_label": format_status(order.order_status),
        "payment_status_label": format_status(order.payment_status),
        "payment_timing_label": format_status(order.payment_timing),
        "payment_method_label": "M-Pesa" if order.payment_method == Order.PaymentMethod.MPESA else "Card",
        "delivery_mode_label": format_status(order.delivery_mode),
        "subtotal_label": format_money(order.subtotal, order.currency),
        "delivery_fee_label": format_money(order.delivery_fee, order.currency),
        "discount_label": format_money(order.discount, order.currency),
        "total_label": get_order_total_label(order),
        "has_discount": order.discount > 0,
        "is_pickup": order.delivery_mode == Order.DeliveryMode.PICKUP,
        "is_parcel": order.delivery_mode == Order.DeliveryMode.PARCEL,
        "is_paid": order.payment_status == Order.PaymentStatus.PAID,
        "needs_manual_delivery_fee": order.manual_delivery_fee_confirmation_required,
    }


def build_cancellation_context(cancellation: OrderCancellation) -> dict:
    order = cancellation.order
    cancelled_items = [
        {
            "name": item.order_item.product_name,
            "quantity": item.quantity,
            "unit_price": format_money(item.unit_price, order.currency),
            "line_total": format_money(item.line_total, order.currency),
        }
        for item in cancellation.items.select_related("order_item").all()
    ]
    cancelled_total = sum(item.line_total for item in cancellation.items.all())

    return {
        **build_order_context(
            order,
            headline="Cancellation confirmed.",
            intro=(
                f"we have cancelled the selected item(s) from order {order.order_number}. "
                "Your updated order details are below."
            ),
        ),
        "cancellation": cancellation,
        "cancelled_items": cancelled_items,
        "cancelled_total_label": format_money(cancelled_total, order.currency),
        "reason_label": cancellation.get_reason_display(),
    }


def render_templated_email(
    *,
    subject: str,
    template_name: str,
    context: dict,
) -> TemplatedEmail:
    text_body = render_to_string(
        f"notifications/text/{template_name}.txt",
        context,
    ).strip()
    html_body = render_to_string(
        f"notifications/email/{template_name}.html",
        context,
    ).strip()

    return TemplatedEmail(
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_templated_email(
    *,
    subject: str,
    template_name: str,
    context: dict,
    recipients: list[str],
) -> None:
    if not recipients:
        return

    email = render_templated_email(
        subject=subject,
        template_name=template_name,
        context=context,
    )
    message = EmailMultiAlternatives(
        subject=email.subject,
        body=email.text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    message.attach_alternative(email.html_body, "text/html")
    message.send(fail_silently=False)
