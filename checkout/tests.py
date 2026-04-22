from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Product, ProductVariant
from checkout.models import DeliveryZone, PickupLocation


class CheckoutQuoteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.product = Product.objects.get(slug="obsidian-power-blazer")
        self.variant = ProductVariant.objects.filter(product=self.product, stock__gte=2).first()
        if self.variant is None:
            self.variant = ProductVariant.objects.filter(product=self.product).first()
            self.variant.stock = 4
            self.variant.save(update_fields=["stock"])

        DeliveryZone.objects.all().delete()
        PickupLocation.objects.all().delete()

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
        DeliveryZone.objects.create(
            name="Nairobi Rider Zone",
            delivery_mode="rider",
            counties=["Nairobi"],
            towns=["Westlands", "Roysambu", "Kilimani"],
            delivery_fee=300,
            manual_fee_confirmation_required=False,
            allow_pay_on_delivery=True,
            estimated_window="2-3 business days",
            priority=10,
            is_active=True,
        )
        DeliveryZone.objects.create(
            name="Kenya Parcel Zone",
            delivery_mode="parcel",
            counties=[],
            towns=[],
            delivery_fee=0,
            manual_fee_confirmation_required=False,
            allow_pay_on_delivery=False,
            estimated_window="3-5 business days",
            priority=100,
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

    def test_pickup_quote_is_prepay_only_with_zero_delivery_fee(self):
        response = self.client.post(
            "/api/v1/checkout/quote",
            {
                "cart": self.build_cart(),
                "deliveryDetails": {
                    "fullName": "Akinyi Otieno",
                    "email": "akinyi@example.com",
                    "phone": "+254700000000",
                    "deliveryMethod": "pickup",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["deliveryMode"], "pickup")
        self.assertEqual(response.data["deliveryFee"], 0)
        self.assertFalse(response.data["manualDeliveryFeeConfirmationRequired"])
        self.assertEqual(
            [option["key"] for option in response.data["availablePaymentOptions"]],
            ["mpesa-prepay"],
        )
        self.assertEqual(
            response.data["pickupInstructions"]["streetAddress"],
            "Lumumba Drive, Roysambu",
        )

    def test_rider_delivery_allows_mpesa_pay_on_delivery(self):
        response = self.client.post(
            "/api/v1/checkout/quote",
            {
                "cart": self.build_cart(),
                "deliveryDetails": {
                    "fullName": "Akinyi Otieno",
                    "email": "akinyi@example.com",
                    "phone": "+254700000000",
                    "county": "Nairobi",
                    "town": "Westlands",
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["deliveryMode"], "rider")
        self.assertEqual(response.data["deliveryFee"], 300)
        self.assertEqual(response.data["paymentSelection"]["timing"], "pay_on_delivery")

    def test_invalid_pay_on_delivery_option_is_rejected_for_card(self):
        response = self.client.post(
            "/api/v1/checkout/quote",
            {
                "cart": self.build_cart(),
                "deliveryDetails": {
                    "fullName": "Akinyi Otieno",
                    "email": "akinyi@example.com",
                    "phone": "+254700000000",
                    "county": "Nairobi",
                    "town": "Westlands",
                    "streetAddress": "Rhapta Road",
                    "deliveryMethod": "delivery",
                },
                "paymentSelection": {
                    "method": "card",
                    "timing": "pay_on_delivery",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not available", response.data["detail"])

    def test_parcel_delivery_requires_prepay_without_manual_fee_confirmation(self):
        response = self.client.post(
            "/api/v1/checkout/quote",
            {
                "cart": self.build_cart(),
                "deliveryDetails": {
                    "fullName": "Akinyi Otieno",
                    "email": "akinyi@example.com",
                    "phone": "+254700000000",
                    "county": "Mombasa",
                    "town": "Nyali",
                    "streetAddress": "Links Road",
                    "deliveryMethod": "delivery",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["deliveryMode"], "parcel")
        self.assertFalse(response.data["manualDeliveryFeeConfirmationRequired"])
        self.assertEqual(
            [option["key"] for option in response.data["availablePaymentOptions"]],
            ["mpesa-prepay"],
        )

    def test_pickup_info_endpoint_returns_active_location(self):
        response = self.client.get("/api/v1/checkout/pickup-info")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["town"], "Roysambu")
        self.assertEqual(response.data["collectionWindowHours"], 72)
