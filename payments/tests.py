from django.core import mail
from django.test import TestCase, override_settings
from unittest.mock import patch
from rest_framework.test import APIClient

from customers.models import CustomerProfile
from orders.models import Order
from payments.models import PaymentTransaction, Receipt


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="orders@wahifashion.com",
    SASAPAY_BASE_URL="https://sandbox.sasapay.app",
    SASAPAY_CLIENT_ID="client-id",
    SASAPAY_CLIENT_SECRET="client-secret",
    SASAPAY_MERCHANT_CODE="600980",
    SASAPAY_CALLBACK_URL="https://example.com/api/v1/payments/sasapay/callback",
)
class SasaPayPaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = CustomerProfile.objects.create(
            supabase_user_id="payment-user-1",
            email="payments@example.com",
            first_name="Naliaka",
            last_name="Atieno",
        )
        self.order = Order.objects.create(
            customer=self.customer,
            order_number="WF-2026-22001",
            delivery_details={
                "fullName": "Naliaka Atieno",
                "email": "payments@example.com",
                "phone": "+254711000000",
                "county": "Nairobi",
                "town": "Westlands",
                "streetAddress": "Ring Road",
                "deliveryMethod": "delivery",
            },
            subtotal=8500,
            delivery_fee=300,
            discount=0,
            total=8800,
            currency="KES",
            delivery_mode="rider",
            payment_method="mpesa",
            payment_timing="prepay",
            payment_status="pending",
            order_status="awaiting_payment",
            manual_delivery_fee_confirmation_required=False,
        )

    @patch("payments.services._request_sasapay")
    def test_checkout_endpoint_creates_transaction_and_returns_checkout_url(self, mock_request):
        mock_request.side_effect = [
            {
                "status": True,
                "detail": "SUCCESS",
                "access_token": "sandbox-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            {
                "status": True,
                "detail": "Redirect the customer to the given checkout url",
                "MerchantRequestID": "MRI-123",
                "CheckoutRequestID": "CRI-456",
                "ResponseCode": "0",
                "ResponseDescription": "Success. Request accepted for processing",
                "CheckoutUrl": "https://checkout.sasapay.app/session-123",
            },
        ]

        response = self.client.post(
            "/api/v1/payments/sasapay/checkout",
            {
                "orderNumber": self.order.order_number,
                "redirectUrl": "https://wahi-fashion.vercel.app/checkout?order=WF-2026-22001&payment=return",
                "successUrl": "https://wahi-fashion.vercel.app/checkout?order=WF-2026-22001&payment=success",
                "failureUrl": "https://wahi-fashion.vercel.app/checkout?order=WF-2026-22001&payment=failed",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["transaction"]["checkoutRequestId"], "CRI-456")
        self.assertEqual(
            response.data["transaction"]["checkoutUrl"],
            "https://checkout.sasapay.app/session-123",
        )
        self.assertEqual(PaymentTransaction.objects.count(), 1)

    @patch("payments.services.verify_sasapay_transaction")
    def test_successful_callback_marks_order_paid_idempotently(self, mock_verify):
        mock_verify.return_value = {
            "statusCode": 0,
            "detail": "Transaction Details",
            "data": {
                "TransID": "SPEJ12345",
                "TransAmount": "8800.00",
            },
        }
        transaction_record = PaymentTransaction.objects.create(
            order=self.order,
            payment_method="mpesa",
            status="pending",
            amount=self.order.total,
            currency="KES",
            merchant_reference=self.order.order_number,
            merchant_request_id="MRI-123",
            checkout_request_id="CRI-456",
            checkout_url="https://checkout.sasapay.app/session-123",
        )

        payload = {
            "ResultCode": "0",
            "ResultDesc": "Transaction processed successfully.",
            "CheckoutRequestID": "CRI-456",
            "MerchantRequestID": "MRI-123",
            "TransactionCode": "SPEJ12345",
            "TransAmount": "8800.00",
            "BillRefNumber": self.order.order_number,
        }

        with self.captureOnCommitCallbacks(execute=True):
            first_response = self.client.post(
                "/api/v1/payments/sasapay/callback",
                payload,
                format="json",
            )
            second_response = self.client.post(
                "/api/v1/payments/sasapay/callback",
                payload,
                format="json",
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.order.refresh_from_db()
        transaction_record.refresh_from_db()
        self.assertEqual(self.order.payment_status, "paid")
        self.assertEqual(self.order.order_status, "paid")
        self.assertEqual(transaction_record.status, "paid")
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(Receipt.objects.filter(order=self.order).count(), 1)
        receipt = Receipt.objects.get(order=self.order)
        self.assertEqual(receipt.status, Receipt.Status.SENT)
        self.assertEqual(receipt.payment_transaction, transaction_record)
        self.assertTrue(
            any(receipt.receipt_number in message.subject for message in mail.outbox)
        )

    @patch("payments.services._request_sasapay")
    def test_status_sync_keeps_payment_pending_without_definitive_confirmation(self, mock_request):
        mock_request.side_effect = [
            {
                "status": True,
                "detail": "SUCCESS",
                "access_token": "sandbox-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            {
                "ResultCode": "0",
                "ResultDescription": "Transaction completed successfully",
                "CheckoutRequestID": "CRI-456",
                "MerchantReference": self.order.order_number,
                "Paid": False,
                "RequestedAmount": "8800.00",
            },
        ]
        PaymentTransaction.objects.create(
            order=self.order,
            payment_method="mpesa",
            status="pending",
            amount=self.order.total,
            currency="KES",
            merchant_reference=self.order.order_number,
            merchant_request_id="MRI-123",
            checkout_request_id="CRI-456",
            checkout_url="https://checkout.sasapay.app/session-123",
        )

        response = self.client.post(
            "/api/v1/payments/sasapay/status-sync",
            {"orderNumber": self.order.order_number},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "pending")
        self.assertEqual(self.order.order_status, "awaiting_payment")
