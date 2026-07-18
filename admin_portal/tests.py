from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient

from admin_portal.models import AdminStaffAccess
from catalog.models import Product, ProductVariant
from customers.models import CustomerProfile
from orders.models import Order
from payments.models import PaymentTransaction, Receipt
from wishlist.models import WishlistItem
from checkout.models import DeliverySettings, PickupLocation


class AdminPortalAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = CustomerProfile.objects.create(
            supabase_user_id="owner-user-1",
            email="owner@wahi.test",
            first_name="Owner",
            last_name="One",
        )
        self.attendant = CustomerProfile.objects.create(
            supabase_user_id="attendant-user-1",
            email="attendant@wahi.test",
            first_name="Attendant",
            last_name="One",
        )
        self.non_staff = CustomerProfile.objects.create(
            supabase_user_id="customer-user-1",
            email="customer@wahi.test",
            first_name="Customer",
            last_name="One",
        )
        AdminStaffAccess.objects.create(
            customer=self.owner,
            role=AdminStaffAccess.Role.OWNER,
        )
        AdminStaffAccess.objects.create(
            customer=self.attendant,
            role=AdminStaffAccess.Role.ATTENDANT,
        )

    def test_owner_can_load_admin_me(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/api/v1/admin/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], AdminStaffAccess.Role.OWNER)
        self.assertEqual(response.json()["email"], "owner@wahi.test")

    def test_attendant_can_load_permissions(self):
        self.client.force_authenticate(user=self.attendant)

        response = self.client.get("/api/v1/admin/permissions")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["orders"]["manage"])
        self.assertFalse(payload["settings"]["view"])
        self.assertFalse(payload["staff"]["manage"])

    def test_non_staff_is_forbidden(self):
        self.client.force_authenticate(user=self.non_staff)

        response = self.client.get("/api/v1/admin/me")

        self.assertEqual(response.status_code, 403)


class AdminStaffManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = CustomerProfile.objects.create(
            supabase_user_id="owner-user-2",
            email="owner2@wahi.test",
            first_name="Owner",
            last_name="Two",
        )
        self.attendant = CustomerProfile.objects.create(
            supabase_user_id="attendant-user-2",
            email="attendant2@wahi.test",
            first_name="Attendant",
            last_name="Two",
        )
        self.candidate = CustomerProfile.objects.create(
            supabase_user_id="candidate-user-1",
            email="candidate@wahi.test",
            first_name="Candidate",
            last_name="One",
        )
        self.owner_access = AdminStaffAccess.objects.create(
            customer=self.owner,
            role=AdminStaffAccess.Role.OWNER,
        )
        self.attendant_access = AdminStaffAccess.objects.create(
            customer=self.attendant,
            role=AdminStaffAccess.Role.ATTENDANT,
        )

    def test_owner_can_list_staff(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/api/v1/admin/staff")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_owner_can_create_staff_access_by_email(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            "/api/v1/admin/staff",
            {
                "email": "candidate@wahi.test",
                "role": AdminStaffAccess.Role.ATTENDANT,
                "isActive": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            AdminStaffAccess.objects.filter(customer=self.candidate).exists()
        )

    def test_owner_can_update_staff_role_and_status(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            f"/api/v1/admin/staff/{self.attendant_access.pk}",
            {
                "role": AdminStaffAccess.Role.OWNER,
                "isActive": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.attendant_access.refresh_from_db()
        self.assertEqual(self.attendant_access.role, AdminStaffAccess.Role.OWNER)
        self.assertFalse(self.attendant_access.is_active)

    def test_attendant_cannot_manage_staff(self):
        self.client.force_authenticate(user=self.attendant)

        response = self.client.get("/api/v1/admin/staff")

        self.assertEqual(response.status_code, 403)

    def test_duplicate_staff_link_is_rejected(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            "/api/v1/admin/staff",
            {
                "email": "attendant2@wahi.test",
                "role": AdminStaffAccess.Role.ATTENDANT,
                "isActive": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)


class AdminDashboardSummaryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = CustomerProfile.objects.create(
            supabase_user_id="summary-owner-1",
            email="summary-owner@wahi.test",
            first_name="Summary",
            last_name="Owner",
        )
        AdminStaffAccess.objects.create(
            customer=self.owner,
            role=AdminStaffAccess.Role.OWNER,
        )
        self.customer = CustomerProfile.objects.create(
            supabase_user_id="summary-customer-1",
            email="summary-customer@wahi.test",
            first_name="Summary",
            last_name="Customer",
        )
        self.product = Product.objects.get(slug="obsidian-power-blazer")
        ProductVariant.objects.update(stock=10)
        self.variant = ProductVariant.objects.filter(product=self.product).first()
        self.variant.stock = 2
        self.variant.save(update_fields=["stock", "updated_at"])

    def create_order(self, order_number: str, payment_status: str, order_status: str) -> Order:
        return Order.objects.create(
            customer=self.customer,
            order_number=order_number,
            delivery_details={"deliveryMethod": "delivery"},
            subtotal=1000,
            delivery_fee=0,
            discount=0,
            total=1000,
            currency="KES",
            payment_method="mpesa",
            payment_status=payment_status,
            payment_timing="prepay",
            delivery_mode="rider",
            order_status=order_status,
        )

    def test_staff_can_load_operational_summary(self):
        awaiting_order = self.create_order(
            "WF-2026-71001",
            Order.PaymentStatus.PENDING,
            Order.OrderStatus.AWAITING_PAYMENT,
        )
        paid_order = self.create_order(
            "WF-2026-71002",
            Order.PaymentStatus.PAID,
            Order.OrderStatus.READY_FOR_DISPATCH,
        )
        PaymentTransaction.objects.create(
            order=awaiting_order,
            payment_method="mpesa",
            status=PaymentTransaction.Status.PENDING,
            amount=awaiting_order.total,
            currency="KES",
            merchant_reference=awaiting_order.order_number,
        )
        PaymentTransaction.objects.create(
            order=paid_order,
            payment_method="mpesa",
            status=PaymentTransaction.Status.PAID,
            amount=paid_order.total,
            currency="KES",
            merchant_reference=paid_order.order_number,
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/api/v1/admin/dashboard-summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["awaitingPaymentOrders"], 1)
        self.assertEqual(payload["fulfillmentActionOrders"], 1)
        self.assertGreaterEqual(payload["lowStockVariants"], 1)
        self.assertEqual(payload["paymentIssueCount"], 1)
        self.assertEqual(payload["recentPaidOrders"][0]["orderNumber"], "WF-2026-71002")
        self.assertEqual(payload["paymentIssues"][0]["orderNumber"], "WF-2026-71001")
        self.assertTrue(
            any(item["sku"] == self.variant.sku for item in payload["lowStockItems"])
        )

    def test_non_staff_cannot_load_operational_summary(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get("/api/v1/admin/dashboard-summary")

        self.assertEqual(response.status_code, 403)


class AdminOrderPaymentCustomerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = CustomerProfile.objects.create(
            supabase_user_id="ops-owner-1",
            email="ops-owner@wahi.test",
            first_name="Ops",
            last_name="Owner",
        )
        self.customer = CustomerProfile.objects.create(
            supabase_user_id="ops-customer-1",
            email="ops-customer@wahi.test",
            first_name="Nia",
            last_name="Achieng",
            phone="+254711222333",
        )
        AdminStaffAccess.objects.create(
            customer=self.owner,
            role=AdminStaffAccess.Role.OWNER,
        )
        self.product = Product.objects.get(slug="obsidian-power-blazer")
        self.variant = ProductVariant.objects.filter(product=self.product).first()
        self.order = Order.objects.create(
            customer=self.customer,
            order_number="WF-2026-81001",
            delivery_details={"deliveryMethod": "delivery"},
            subtotal=1000,
            delivery_fee=300,
            discount=0,
            total=1300,
            currency="KES",
            payment_method="mpesa",
            payment_status=Order.PaymentStatus.PENDING,
            payment_timing=Order.PaymentTiming.PREPAY,
            delivery_mode=Order.DeliveryMode.RIDER,
            order_status=Order.OrderStatus.AWAITING_PAYMENT,
        )
        self.payment = PaymentTransaction.objects.create(
            order=self.order,
            payment_method="mpesa",
            status=PaymentTransaction.Status.PENDING,
            amount=self.order.total,
            currency="KES",
            merchant_reference=self.order.order_number,
            transaction_code="TXN-81001",
        )
        WishlistItem.objects.create(customer=self.customer, product=self.product)

    def authenticate_owner(self):
        self.client.force_authenticate(user=self.owner)

    def test_staff_can_filter_orders(self):
        self.authenticate_owner()

        response = self.client.get(
            "/api/v1/admin/orders",
            {"paymentStatus": Order.PaymentStatus.PENDING, "q": "81001"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["orderNumber"], "WF-2026-81001")

    def test_staff_can_update_order_status_and_notes(self):
        self.authenticate_owner()

        response = self.client.patch(
            "/api/v1/admin/orders/WF-2026-81001",
            {
                "orderStatus": Order.OrderStatus.READY_FOR_DISPATCH,
                "paymentStatus": Order.PaymentStatus.PAID,
                "internalNotes": "Confirmed manually by owner.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, Order.OrderStatus.READY_FOR_DISPATCH)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.internal_notes, "Confirmed manually by owner.")

    def test_staff_can_mark_pay_on_delivery_order_paid_and_issue_receipt(self):
        pod_order = Order.objects.create(
            customer=self.customer,
            order_number="WF-2026-81002",
            delivery_details={
                "deliveryMethod": "delivery",
                "fullName": "Nia Achieng",
                "phone": "+254711222333",
                "streetAddress": "Lumumba Drive",
                "town": "Roysambu",
                "county": "Nairobi",
            },
            subtotal=2000,
            delivery_fee=200,
            discount=0,
            total=2200,
            currency="KES",
            payment_method="mpesa",
            payment_status=Order.PaymentStatus.MANUAL_ON_DELIVERY,
            payment_timing=Order.PaymentTiming.PAY_ON_DELIVERY,
            delivery_mode=Order.DeliveryMode.RIDER,
            order_status=Order.OrderStatus.NEW,
        )
        self.authenticate_owner()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/admin/orders/WF-2026-81002/mark-paid",
                {
                    "amountCollected": 2200,
                    "paymentMethod": "mpesa",
                    "paymentReference": "POD-MPESA-001",
                    "staffNote": "Collected by rider.",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        pod_order.refresh_from_db()
        receipt = Receipt.objects.get(order=pod_order)
        self.assertEqual(pod_order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(receipt.payment_reference, "POD-MPESA-001")
        self.assertEqual(receipt.status, Receipt.Status.SENT)
        self.assertIn("receipt", response.json())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(receipt.receipt_number, mail.outbox[0].subject)

    def test_mark_paid_rejects_prepaid_order(self):
        self.authenticate_owner()

        response = self.client.post(
            "/api/v1/admin/orders/WF-2026-81001/mark-paid",
            {
                "amountCollected": 1300,
                "paymentMethod": "mpesa",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Receipt.objects.filter(order=self.order).exists())

    def test_staff_can_resend_existing_receipt(self):
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save(update_fields=["payment_status", "updated_at"])
        receipt = Receipt.objects.create(
            order=self.order,
            receipt_number="WAHI-RCPT-2026-81001",
            total_paid=self.order.total,
            currency=self.order.currency,
            payment_method=self.order.payment_method,
            payment_reference="TXN-81001",
        )
        self.authenticate_owner()

        response = self.client.post("/api/v1/admin/orders/WF-2026-81001/receipt/resend")

        self.assertEqual(response.status_code, 200)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, Receipt.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_staff_can_list_and_view_payments(self):
        self.authenticate_owner()

        list_response = self.client.get(
            "/api/v1/admin/payments",
            {"status": PaymentTransaction.Status.PENDING, "q": "TXN-81001"},
        )
        detail_response = self.client.get(f"/api/v1/admin/payments/{self.payment.pk}")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()[0]["orderNumber"], "WF-2026-81001")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["transactionCode"], "TXN-81001")

    def test_staff_can_search_and_view_customer_detail(self):
        self.authenticate_owner()

        list_response = self.client.get("/api/v1/admin/customers", {"q": "Nia"})
        detail_response = self.client.get(f"/api/v1/admin/customers/{self.customer.pk}")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()[0]["email"], "ops-customer@wahi.test")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["recentOrders"][0]["orderNumber"], "WF-2026-81001")
        self.assertEqual(detail_response.json()["wishlist"][0]["slug"], self.product.slug)


class AdminCatalogInventorySettingsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = CustomerProfile.objects.create(
            supabase_user_id="catalog-owner-1",
            email="catalog-owner@wahi.test",
        )
        self.attendant = CustomerProfile.objects.create(
            supabase_user_id="catalog-attendant-1",
            email="catalog-attendant@wahi.test",
        )
        AdminStaffAccess.objects.create(customer=self.owner, role=AdminStaffAccess.Role.OWNER)
        AdminStaffAccess.objects.create(customer=self.attendant, role=AdminStaffAccess.Role.ATTENDANT)
        self.product = Product.objects.get(slug="obsidian-power-blazer")
        self.variant = ProductVariant.objects.filter(product=self.product).first()

    def test_owner_can_update_product_and_create_variant(self):
        self.client.force_authenticate(user=self.owner)

        product_response = self.client.patch(
            f"/api/v1/admin/products/{self.product.pk}",
            {
                "external_id": self.product.external_id,
                "slug": self.product.slug,
                "name": "Updated Blazer",
                "brand": self.product.brand,
                "categorySlug": self.product.category.slug,
                "description": self.product.description,
                "images": self.product.images,
                "price": self.product.price,
                "originalPrice": self.product.original_price,
                "currency": self.product.currency,
                "tags": self.product.tags,
                "rating": str(self.product.rating),
                "review_count": self.product.review_count,
                "isFeatured": self.product.is_featured,
                "isNewArrival": self.product.is_new_arrival,
                "material": self.product.material,
                "careInstructions": self.product.care_instructions,
                "created_at": self.product.created_at.isoformat(),
            },
            format="json",
        )
        variant_response = self.client.post(
            f"/api/v1/admin/products/{self.product.pk}/variants",
            {
                "external_id": "variant-admin-test",
                "size": "M",
                "color": "Gold",
                "colorHex": "#d4a853",
                "imageUrl": "https://example.com/gold-blazer.jpg",
                "stock": 4,
                "sku": "ADMIN-TEST-001",
            },
            format="json",
        )

        self.assertEqual(product_response.status_code, 200)
        self.assertEqual(product_response.json()["name"], "Updated Blazer")
        self.assertEqual(variant_response.status_code, 201)
        self.assertEqual(variant_response.json()["sku"], "ADMIN-TEST-001")
        self.assertEqual(variant_response.json()["imageUrl"], "https://example.com/gold-blazer.jpg")

    def test_owner_can_create_product_and_variant_without_external_ids(self):
        self.client.force_authenticate(user=self.owner)

        product_response = self.client.post(
            "/api/v1/admin/products",
            {
                "slug": "owner-created-product",
                "name": "Owner Created Product",
                "brand": "Wahi Fashion",
                "categorySlug": self.product.category.slug,
                "description": "Created from admin dashboard.",
                "images": ["https://example.com/product.jpg"],
                "price": 3200,
                "originalPrice": None,
                "currency": "KES",
                "badge": "",
                "tags": [],
                "rating": "0",
                "review_count": 0,
                "isFeatured": False,
                "isNewArrival": False,
                "material": "",
                "careInstructions": "",
                "created_at": self.product.created_at.isoformat(),
            },
            format="json",
        )

        self.assertEqual(product_response.status_code, 201)
        self.assertTrue(product_response.json()["id"].startswith("prod-"))
        self.assertEqual(str(product_response.json()["adminId"]), str(Product.objects.get(external_id=product_response.json()["id"]).pk))

        created_product = Product.objects.get(external_id=product_response.json()["id"])
        variant_response = self.client.post(
            f"/api/v1/admin/products/{created_product.pk}/variants",
            {
                "size": "One Size",
                "color": "Gold",
                "colorHex": "#d4a853",
                "stock": 5,
            },
            format="json",
        )

        self.assertEqual(variant_response.status_code, 201)
        self.assertTrue(variant_response.json()["id"].startswith("variant-"))
        self.assertEqual(str(variant_response.json()["adminId"]), str(ProductVariant.objects.get(external_id=variant_response.json()["id"]).pk))
        self.assertTrue(variant_response.json()["sku"])

    def test_attendant_can_update_stock_but_not_settings(self):
        self.client.force_authenticate(user=self.attendant)

        stock_response = self.client.patch(
            f"/api/v1/admin/variants/{self.variant.pk}/stock",
            {"stock": 9},
            format="json",
        )
        zone_response = self.client.patch(
            "/api/v1/admin/delivery-settings",
            {
                "name": "Blocked Settings",
                "shopName": "Wahi Fashion Roysambu",
                "shopCounty": "Nairobi",
                "shopTown": "Roysambu",
                "shopStreetAddress": "Lumumba Drive, Roysambu",
                "shopLatitude": -1.218257,
                "shopLongitude": 36.886459,
                "riderMaxRadiusKm": 50,
                "parcelSwitchRadiusKm": 50,
                "riderBaseFee": 200,
                "riderIncrementPer10Km": 200,
                "riderEstimatedWindow": "2-3 business days",
                "parcelEstimatedWindow": "Dispatch arranged after payment confirmation",
                "allowPayOnDelivery": True,
                "parcelManualFeeConfirmationRequired": True,
                "isActive": True,
            },
            format="json",
        )

        self.assertEqual(stock_response.status_code, 200)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 9)
        self.assertEqual(zone_response.status_code, 403)

    def test_owner_can_manage_delivery_settings_and_pickup_location(self):
        self.client.force_authenticate(user=self.owner)

        settings_response = self.client.patch(
            "/api/v1/admin/delivery-settings",
            {
                "name": "Primary Delivery Settings",
                "shopName": "Wahi Fashion Roysambu",
                "shopCounty": "Nairobi",
                "shopTown": "Roysambu",
                "shopStreetAddress": "Lumumba Drive, Roysambu",
                "shopLatitude": -1.218257,
                "shopLongitude": 36.886459,
                "riderMaxRadiusKm": 60,
                "parcelSwitchRadiusKm": 60,
                "riderBaseFee": 200,
                "riderIncrementPer10Km": 250,
                "riderEstimatedWindow": "1-2 days",
                "parcelEstimatedWindow": "Manual parcel dispatch",
                "allowPayOnDelivery": True,
                "parcelManualFeeConfirmationRequired": True,
                "isActive": True,
            },
            format="json",
        )
        pickup_response = self.client.post(
            "/api/v1/admin/pickup-locations",
            {
                "name": "Admin Pickup",
                "county": "Nairobi",
                "town": "Roysambu",
                "streetAddress": "Lumumba Drive",
                "contactName": "Wahi",
                "contactPhone": "+254700000000",
                "mapsUrl": "https://maps.google.com",
                "openingHours": "Mon-Sat",
                "collectionWindowHours": 72,
                "notes": "Bring order number",
                "isActive": True,
            },
            format="json",
        )

        self.assertEqual(settings_response.status_code, 200)
        self.assertTrue(DeliverySettings.objects.filter(rider_max_radius_km=60).exists())
        self.assertEqual(pickup_response.status_code, 201)
        self.assertTrue(PickupLocation.objects.filter(name="Admin Pickup").exists())

    def test_inactive_staff_is_forbidden(self):
        self.client.force_authenticate(user=self.owner)
        staff_access = self.owner.admin_staff_access
        staff_access.is_active = False
        staff_access.save(update_fields=["is_active", "updated_at"])

        response = self.client.get("/api/v1/admin/permissions")

        self.assertEqual(response.status_code, 403)
