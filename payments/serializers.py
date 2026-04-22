from rest_framework import serializers

from orders.serializers import OrderSerializer
from payments.models import PaymentTransaction


class SasaPayCheckoutSerializer(serializers.Serializer):
    orderNumber = serializers.CharField()
    redirectUrl = serializers.URLField()
    successUrl = serializers.URLField()
    failureUrl = serializers.URLField()


class SasaPayStatusSyncSerializer(serializers.Serializer):
    orderNumber = serializers.CharField()


class PaymentTransactionSerializer(serializers.ModelSerializer):
    provider = serializers.CharField()
    paymentMethod = serializers.CharField(source="payment_method")
    merchantReference = serializers.CharField(source="merchant_reference")
    merchantRequestId = serializers.CharField(source="merchant_request_id")
    checkoutRequestId = serializers.CharField(source="checkout_request_id")
    transactionCode = serializers.CharField(source="transaction_code")
    checkoutUrl = serializers.CharField(source="checkout_url")
    providerResponse = serializers.JSONField(source="provider_response")
    callbackPayload = serializers.JSONField(source="callback_payload")
    lastStatusPayload = serializers.JSONField(source="last_status_payload")
    verificationPayload = serializers.JSONField(source="verification_payload")
    paidAt = serializers.DateTimeField(source="paid_at", allow_null=True)
    failedAt = serializers.DateTimeField(source="failed_at", allow_null=True)
    lastSyncedAt = serializers.DateTimeField(source="last_synced_at", allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = PaymentTransaction
        fields = (
            "provider",
            "status",
            "paymentMethod",
            "amount",
            "currency",
            "merchantReference",
            "merchantRequestId",
            "checkoutRequestId",
            "transactionCode",
            "checkoutUrl",
            "providerResponse",
            "callbackPayload",
            "lastStatusPayload",
            "verificationPayload",
            "paidAt",
            "failedAt",
            "lastSyncedAt",
            "createdAt",
            "updatedAt",
        )


class SasaPayPaymentResponseSerializer(serializers.Serializer):
    order = OrderSerializer()
    transaction = PaymentTransactionSerializer()
