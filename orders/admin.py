from django.contrib import admin

from common.admin_mixins import AttendantRestrictedFieldsMixin, ReadOnlyInlineMixin
from common.admin_roles import is_attendant, is_owner
from orders.models import Order, OrderItem


class OrderItemInline(ReadOnlyInlineMixin, admin.TabularInline):
    model = OrderItem
    readonly_fields = (
        "product",
        "variant_id",
        "quantity",
        "product_name",
        "product_image",
        "price",
        "currency",
        "size",
        "color",
        "color_hex",
    )


@admin.register(Order)
class OrderAdmin(AttendantRestrictedFieldsMixin, admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer",
        "guest_email",
        "delivery_mode",
        "total",
        "payment_method",
        "payment_timing",
        "payment_status",
        "order_status",
        "payment_expires_at",
        "created_at",
    )
    list_filter = (
        "delivery_mode",
        "payment_method",
        "payment_timing",
        "payment_status",
        "order_status",
        "created_at",
    )
    search_fields = ("order_number", "customer__email", "guest_email")
    readonly_fields = (
        "order_number",
        "customer",
        "guest_email",
        "delivery_details",
        "subtotal",
        "delivery_fee",
        "discount",
        "total",
        "currency",
        "delivery_mode",
        "payment_method",
        "payment_timing",
        "manual_delivery_fee_confirmation_required",
        "payment_expires_at",
        "pickup_instructions",
        "created_at",
        "updated_at",
    )
    attendant_readonly_fields = readonly_fields
    inlines = [OrderItemInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return is_owner(request.user)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if is_attendant(request.user) and not is_owner(request.user):
            readonly_fields.extend(("payment_status", "order_status", "internal_notes"))
            for editable_field in ("payment_status", "order_status", "internal_notes"):
                if editable_field in readonly_fields:
                    readonly_fields.remove(editable_field)

        return tuple(dict.fromkeys(readonly_fields))


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_name", "quantity", "price", "size", "color")
    search_fields = ("order__order_number", "product_name", "variant_id")
    readonly_fields = (
        "order",
        "product",
        "variant_id",
        "quantity",
        "product_name",
        "product_image",
        "price",
        "currency",
        "size",
        "color",
        "color_hex",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
