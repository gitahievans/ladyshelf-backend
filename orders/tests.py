from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import Product, ProductVariant
from customers.models import CustomerProfile
from orders.expiry import expire_unpaid_prepay_orders
from orders.models import Order, OrderItem
from payments.models import PaymentTransaction


class AccountOrderHistoryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = CustomerProfile.objects.create(
            supabase_user_id="orders-user-1",
            email="orders@example.com",
            first_name="Akinyi",
            last_name="Otieno",
        )
        self.product = Product.objects.get(slug="obsidian-power-blazer")
        self.variant = ProductVariant.objects.filter(product=self.product).first()

    def test_authenticated_user_can_list_their_orders(self):
        order = Order.objects.create(
            customer=self.customer,
            order_number="WF-2026-11001",
            delivery_details={
                "fullName": "Akinyi Otieno",
                "email": "orders@example.com",
                "phone": "+254700000000",
                "county": "Nairobi",
                "town": "Roysambu",
                "streetAddress": "Lumumba Drive",
                "deliveryMethod": "delivery",
            },
            subtotal=7800,
            delivery_fee=300,
            discount=0,
            total=8100,
            currency="KES",
            payment_method="mpesa",
            payment_status="paid",
            payment_timing="prepay",
            delivery_mode="rider",
            order_status="awaiting_payment",
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            variant_id=self.variant.external_id,
            quantity=1,
            product_name=self.product.name,
            product_image=self.product.images[0],
            price=self.product.price,
            currency=self.product.currency,
            size=self.variant.size,
            color=self.variant.color,
            color_hex=self.variant.color_hex,
        )
        self.client.force_authenticate(user=self.customer)

        response = self.client.get("/api/v1/account/orders")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["orderNumber"], "WF-2026-11001")
        self.assertEqual(response.json()[0]["items"][0]["productId"], self.product.external_id)
        self.assertEqual(response.json()[0]["orderStatus"], "awaiting_payment")


class PrepaidOrderExpiryTests(TestCase):
    def setUp(self):
        self.product = Product.objects.get(slug="obsidian-power-blazer")
        self.variant = ProductVariant.objects.filter(product=self.product).first()
        self.variant.stock = 3
        self.variant.save(update_fields=["stock", "updated_at"])

    def create_expired_order(self) -> Order:
        order = Order.objects.create(
            order_number="WF-2026-33001",
            guest_email="guest@example.com",
            delivery_details={
                "fullName": "Brenda Otieno",
                "email": "guest@example.com",
                "phone": "+254700000000",
                "county": "Nairobi",
                "town": "Westlands",
                "streetAddress": "Rhapta Road",
                "deliveryMethod": "delivery",
            },
            subtotal=self.product.price,
            delivery_fee=0,
            discount=0,
            total=self.product.price,
            currency="KES",
            payment_method="mpesa",
            payment_status="pending",
            payment_timing="prepay",
            delivery_mode="rider",
            order_status="awaiting_payment",
            payment_expires_at=timezone.now() - timedelta(minutes=1),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            variant_id=self.variant.external_id,
            quantity=1,
            product_name=self.product.name,
            product_image=self.product.images[0],
            price=self.product.price,
            currency=self.product.currency,
            size=self.variant.size,
            color=self.variant.color,
            color_hex=self.variant.color_hex,
        )
        PaymentTransaction.objects.create(
            order=order,
            payment_method="mpesa",
            status="pending",
            amount=order.total,
            currency="KES",
            merchant_reference=order.order_number,
            merchant_request_id="MRI-33001",
            checkout_request_id="CRI-33001",
            checkout_url="https://checkout.sasapay.app/session-33001",
        )
        self.variant.stock = 2
        self.variant.save(update_fields=["stock", "updated_at"])
        return order

    def test_expiry_cancels_unpaid_prepay_order_and_restores_stock(self):
        order = self.create_expired_order()

        expired_count = expire_unpaid_prepay_orders()

        self.assertEqual(expired_count, 1)
        order.refresh_from_db()
        self.variant.refresh_from_db()
        transaction_record = order.payment_transactions.first()
        self.assertEqual(order.order_status, "cancelled")
        self.assertEqual(order.payment_status, "failed")
        self.assertIn("Auto-cancelled after 30 minutes", order.internal_notes)
        self.assertEqual(self.variant.stock, 3)
        self.assertEqual(transaction_record.status, "failed")

    def test_management_command_expires_unpaid_orders(self):
        order = self.create_expired_order()

        call_command("expire_unpaid_prepay_orders")

        order.refresh_from_db()
        self.assertEqual(order.order_status, "cancelled")

    def test_expiry_skips_paid_and_pay_on_delivery_orders(self):
        paid_order = Order.objects.create(
            order_number="WF-2026-33002",
            guest_email="paid@example.com",
            delivery_details={"deliveryMethod": "delivery"},
            subtotal=1000,
            delivery_fee=0,
            discount=0,
            total=1000,
            currency="KES",
            payment_method="mpesa",
            payment_status="paid",
            payment_timing="prepay",
            delivery_mode="rider",
            order_status="paid",
            payment_expires_at=timezone.now() - timedelta(minutes=10),
        )
        pod_order = Order.objects.create(
            order_number="WF-2026-33003",
            guest_email="pod@example.com",
            delivery_details={"deliveryMethod": "delivery"},
            subtotal=1000,
            delivery_fee=0,
            discount=0,
            total=1000,
            currency="KES",
            payment_method="mpesa",
            payment_status="manual_on_delivery",
            payment_timing="pay_on_delivery",
            delivery_mode="rider",
            order_status="new",
        )

        expired_count = expire_unpaid_prepay_orders()

        self.assertEqual(expired_count, 0)
        paid_order.refresh_from_db()
        pod_order.refresh_from_db()
        self.assertEqual(paid_order.order_status, "paid")
        self.assertEqual(pod_order.order_status, "new")
