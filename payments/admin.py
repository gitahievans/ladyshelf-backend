from django.contrib import admin

from payments.models import PaymentTransaction, Receipt


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "provider",
        "payment_method",
        "status",
        "amount",
        "currency",
        "checkout_request_id",
        "transaction_code",
        "created_at",
    )
    list_filter = ("provider", "payment_method", "status", "currency", "created_at")
    search_fields = (
        "order__order_number",
        "merchant_reference",
        "merchant_request_id",
        "checkout_request_id",
        "transaction_code",
    )
    readonly_fields = (
        "order",
        "provider",
        "payment_method",
        "status",
        "amount",
        "currency",
        "merchant_reference",
        "merchant_request_id",
        "checkout_request_id",
        "transaction_code",
        "checkout_url",
        "provider_response",
        "callback_payload",
        "last_status_payload",
        "verification_payload",
        "paid_at",
        "failed_at",
        "last_synced_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "order",
        "status",
        "total_paid",
        "currency",
        "payment_method",
        "payment_reference",
        "sent_to_email",
        "sent_at",
        "issued_at",
    )
    list_filter = ("status", "payment_method", "currency", "issued_at", "sent_at")
    search_fields = (
        "receipt_number",
        "order__order_number",
        "sent_to_email",
        "payment_reference",
    )
    readonly_fields = (
        "order",
        "payment_transaction",
        "receipt_number",
        "status",
        "issued_at",
        "sent_at",
        "sent_to_email",
        "total_paid",
        "currency",
        "payment_method",
        "payment_reference",
        "created_by",
        "metadata",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
