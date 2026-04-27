from django.contrib import admin

from checkout.models import DeliverySettings, DeliveryZone, PickupLocation


@admin.register(DeliverySettings)
class DeliverySettingsAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "shop_name",
        "rider_max_radius_km",
        "parcel_switch_radius_km",
        "rider_base_fee",
        "rider_increment_per_10km",
        "allow_pay_on_delivery",
        "is_active",
    )
    list_filter = ("allow_pay_on_delivery", "parcel_manual_fee_confirmation_required", "is_active")
    search_fields = ("name", "shop_name", "shop_town", "shop_county", "shop_street_address")


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
