from django.contrib import admin

from checkout.models import DeliveryZone, PickupLocation


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "delivery_mode",
        "delivery_fee",
        "manual_fee_confirmation_required",
        "allow_pay_on_delivery",
        "priority",
        "is_active",
    )
    list_filter = (
        "delivery_mode",
        "manual_fee_confirmation_required",
        "allow_pay_on_delivery",
        "is_active",
    )
    search_fields = ("name",)


@admin.register(PickupLocation)
class PickupLocationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "town",
        "county",
        "contact_phone",
        "collection_window_hours",
        "is_active",
    )
    list_filter = ("is_active", "county")
    search_fields = ("name", "town", "county", "street_address")
