from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.models import Product, ProductVariant
from checkout.models import DeliverySettings, PickupLocation
from customers.models import CustomerProfile
from orders.models import Order


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="orders@wahifashion.com",
    ORDER_NOTIFICATION_STAFF_EMAILS=["studio@wahifashion.com"],
)
class CheckoutOrderCreationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = CustomerProfile.objects.create(
            supabase_user_id="checkout-user-1",
            email="akinyi@example.com",
            first_name="Akinyi",
            last_name="Otieno",
        )
        self.product = Product.objects.get(slug="obsidian-power-blazer")
        self.variant = ProductVariant.objects.filter(product=self.product).first()
        self.variant.stock = 5
        self.variant.save(update_fields=["stock", "updated_at"])

        DeliverySettings.objects.all().delete()
        PickupLocation.objects.all().delete()

        DeliverySettings.objects.create(
            name="Primary Delivery Settings",
            shop_name="Wahi Fashion Roysambu",
            shop_county="Nairobi",
            shop_town="Roysambu",
            shop_street_address="Lumumba Drive, Roysambu",
            shop_latitude=-1.218257,
            shop_longitude=36.886459,
            rider_max_radius_km=50,
            parcel_switch_radius_km=50,
            rider_base_fee=200,
            rider_increment_per_10km=200,
            rider_estimated_window="2-3 business days",
            parcel_estimated_window="Dispatch arranged after payment confirmation",
            allow_pay_on_delivery=True,
            parcel_manual_fee_confirmation_required=True,
            is_active=True,
        )

        PickupLocation.objects.create(
            name="Wahi Fashion Roysambu Pickup",
            county="Nairobi",
            town="Roysambu",
            street_address="Lumumba Drive, Roysambu",
            contact_name="Wahi Fashion",
            contact_phone="+254711000000",
            maps_url="https://maps.google.com/?q=Lumumba+Drive+Roysambu",
            opening_hours="Mon-Sat 9am-7pm",
            collection_window_hours=72,
            notes="Bring your order confirmation when collecting.",
            is_active=True,
        )
    def build_cart(self) -> list[dict]:
        return [
            {
                "productId": self.product.external_id,
                "variantId": self.variant.external_id,
                "quantity": 1,
            }
        ]

    def test_guest_parcel_order_starts_awaiting_payment_without_immediate_emails(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/checkout/orders",
                {
                    "cart": self.build_cart(),
                    "deliveryDetails": {
                        "fullName": "Brenda Otieno",
                        "email": "guest@example.com",
                        "phone": "+254700000000",
                        "county": "Mombasa",
                        "town": "Nyali",
                        "locationLabel": "Nyali, Mombasa",
                        "latitude": -4.0435,
                        "longitude": 39.6682,
                        "streetAddress": "Links Road",
                        "deliveryMethod": "delivery",
                    },
                    "paymentSelection": {
                        "method": "mpesa",
                        "timing": "prepay",
                    },
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["orderStatus"], "awaiting_payment")
        self.assertEqual(response.data["paymentStatus"], "pending")
        self.assertEqual(response.data["guestEmail"], "guest@example.com")
        self.assertTrue(response.data["manualDeliveryFeeConfirmationRequired"])
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 4)
        self.assertEqual(len(mail.outbox), 0)

    def test_authenticated_rider_pay_on_delivery_order_uses_manual_payment_status(self):
        self.client.force_authenticate(user=self.customer)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/checkout/orders",
                {
                    "cart": self.build_cart(),
                    "deliveryDetails": {
                        "fullName": "Akinyi Otieno",
                        "email": "akinyi@example.com",
                        "phone": "+254700000000",
                        "county": "Nairobi",
                        "town": "Westlands",
                        "locationLabel": "Westlands, Nairobi",
                        "latitude": -1.2676,
                        "longitude": 36.8108,
                        "streetAddress": "Rhapta Road",
                        "deliveryMethod": "delivery",
                    },
                    "paymentSelection": {
                        "method": "mpesa",
                        "timing": "pay_on_delivery",
                    },
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["userId"], "checkout-user-1")
        self.assertEqual(response.data["paymentStatus"], "manual_on_delivery")
        self.assertEqual(response.data["orderStatus"], "new")
        self.assertEqual(response.data["paymentTiming"], "pay_on_delivery")
        self.assertEqual(len(mail.outbox), 2)

    def test_pickup_order_starts_awaiting_payment(self):
        response = self.client.post(
            "/api/v1/checkout/orders",
            {
                "cart": self.build_cart(),
                "deliveryDetails": {
                    "fullName": "Moraa Achieng",
                    "email": "moraa@example.com",
                    "phone": "+254711111111",
                    "deliveryMethod": "pickup",
                },
                "paymentSelection": {
                    "method": "mpesa",
                    "timing": "prepay",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["deliveryMode"], "pickup")
        self.assertEqual(response.data["orderStatus"], "awaiting_payment")
        self.assertEqual(response.data["pickupInstructions"]["town"], "Roysambu")


class OrdersReadEndpointsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = CustomerProfile.objects.create(
            supabase_user_id="orders-user-2",
            email="orders@example.com",
            first_name="Akinyi",
            last_name="Otieno",
        )
        self.order = Order.objects.create(
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
            delivery_mode="rider",
            payment_method="mpesa",
            payment_timing="prepay",
            payment_status="pending",
            order_status="awaiting_payment",
        )

    def test_authenticated_user_can_list_orders_from_top_level_endpoint(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get("/api/v1/orders")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["orderNumber"], "WF-2026-11001")

    def test_authenticated_user_can_retrieve_their_order_by_order_number(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(f"/api/v1/orders/{self.order.order_number}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["orderStatus"], "awaiting_payment")
