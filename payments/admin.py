from django.contrib import admin

from payments.models import PaymentTransaction


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
