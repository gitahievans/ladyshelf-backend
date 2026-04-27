from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import Category, Product
from customers.models import CustomerProfile
from notifications.services import (
    send_account_created_notification,
    send_order_created_notifications,
    send_payment_status_notification,
)
from orders.models import Order, OrderItem


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="orders@wahifashion.com",
    ORDER_NOTIFICATION_STAFF_EMAILS=["studio@wahifashion.com"],
)
class NotificationEmailTemplateTests(TestCase):
    def setUp(self):
        self.customer = CustomerProfile.objects.create(
            supabase_user_id="notification-user-1",
            email="akinyi@example.com",
            first_name="Akinyi",
            last_name="Otieno",
            phone="+254700000000",
        )
        self.category, _ = Category.objects.get_or_create(
            slug="email-template-office-formal",
            defaults={
                "external_id": "cat-email-template-office",
                "name": "Office & Formal",
                "description": "Tailored pieces for polished days.",
                "image": "https://example.com/category.jpg",
            },
        )
        self.product, _ = Product.objects.get_or_create(
            external_id="prod-email-template-blazer",
            defaults={
                "slug": "email-template-obsidian-power-blazer",
                "name": "Obsidian Power Blazer",
                "brand": "Wahi Fashion",
                "category": self.category,
                "description": "A composed blazer for strong entrances.",
                "images": ["https://example.com/blazer.jpg"],
                "price": 7800,
                "currency": "KES",
                "tags": ["office"],
                "rating": 4.8,
                "review_count": 12,
                "is_featured": True,
                "is_new_arrival": False,
                "created_at": timezone.now(),
            },
        )
        self.order = Order.objects.create(
            customer=self.customer,
            order_number="WF-2026-33001",
            delivery_details={
                "fullName": "Akinyi Otieno",
                "email": "akinyi@example.com",
                "phone": "+254700000000",
                "county": "Nairobi",
                "town": "Westlands",
                "streetAddress": "Rhapta Road",
                "deliveryMethod": "delivery",
            },
            subtotal=7800,
            delivery_fee=300,
            discount=0,
            total=8100,
            currency="KES",
            delivery_mode=Order.DeliveryMode.RIDER,
            payment_method=Order.PaymentMethod.MPESA,
            payment_timing=Order.PaymentTiming.PAY_ON_DELIVERY,
            payment_status=Order.PaymentStatus.MANUAL_ON_DELIVERY,
            order_status=Order.OrderStatus.NEW,
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            variant_id="variant-blazer-s-black",
            quantity=1,
            product_name=self.product.name,
            product_image=self.product.images[0],
            price=self.product.price,
            currency="KES",
            size="S",
            color="Black",
            color_hex="#111111",
        )

    def test_order_created_email_uses_html_and_text_templates(self):
        send_order_created_notifications(self.order)

        self.assertEqual(len(mail.outbox), 2)
        customer_email = mail.outbox[0]
        staff_email = mail.outbox[1]

        self.assertEqual(customer_email.to, ["akinyi@example.com"])
        self.assertEqual(customer_email.subject, "Wahi Fashion order received: WF-2026-33001")
        self.assertIn("Order WF-2026-33001", customer_email.body)
        self.assertIn("Obsidian Power Blazer", customer_email.body)
        self.assertEqual(customer_email.alternatives[0][1], "text/html")
        self.assertIn("More than fashion. A lifestyle.", customer_email.alternatives[0][0])
        self.assertIn("Lumumba Drive, Roysambu, Nairobi", customer_email.alternatives[0][0])

        self.assertEqual(staff_email.to, ["studio@wahifashion.com"])
        self.assertIn("New order placed", staff_email.subject)
        self.assertIn("Store operations", staff_email.alternatives[0][0])
        self.assertIn("Rhapta Road", staff_email.body)

    def test_payment_failed_email_uses_attention_template(self):
        self.order.payment_status = Order.PaymentStatus.FAILED
        self.order.order_status = Order.OrderStatus.AWAITING_PAYMENT
        self.order.save(update_fields=["payment_status", "order_status", "updated_at"])

        send_payment_status_notification(self.order.pk)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["akinyi@example.com"])
        self.assertEqual(message.subject, "Payment needs attention: WF-2026-33001")
        self.assertIn("We could not confirm payment", message.body)
        self.assertIn("Your order is still reserved.", message.alternatives[0][0])

    def test_account_created_email_template_is_available_for_future_auth_flow(self):
        send_account_created_notification(
            email="zawadi@example.com",
            customer_name="Zawadi",
        )

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Welcome to Wahi Fashion")
        self.assertEqual(message.to, ["zawadi@example.com"])
        self.assertIn("Thank you for joining Wahi Fashion", message.body)
        self.assertIn("Your wardrobe has a new home.", message.alternatives[0][0])
