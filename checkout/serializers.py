from rest_framework import serializers

from checkout.models import DeliverySettings, PickupLocation


class CheckoutCartLineSerializer(serializers.Serializer):
    productId = serializers.CharField()
    variantId = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)


class CheckoutDeliveryDetailsSerializer(serializers.Serializer):
    fullName = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    county = serializers.CharField(allow_blank=True, required=False, default="")
    town = serializers.CharField(allow_blank=True, required=False, default="")
    locationLabel = serializers.CharField(allow_blank=True, required=False, default="")
    latitude = serializers.FloatField(required=False, allow_null=True, default=None)
    longitude = serializers.FloatField(required=False, allow_null=True, default=None)
    streetAddress = serializers.CharField(allow_blank=True, required=False, default="")
    additionalInfo = serializers.CharField(
        allow_blank=True,
        required=False,
        allow_null=True,
        default="",
    )
    deliveryMethod = serializers.ChoiceField(choices=["delivery", "pickup"])


class CheckoutPaymentSelectionSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=["mpesa", "card"])
    timing = serializers.ChoiceField(choices=["prepay", "pay_on_delivery"])


class CheckoutQuoteRequestSerializer(serializers.Serializer):
    cart = CheckoutCartLineSerializer(many=True)
    deliveryDetails = CheckoutDeliveryDetailsSerializer()
    paymentSelection = CheckoutPaymentSelectionSerializer(required=False)


class CheckoutOrderCreateRequestSerializer(serializers.Serializer):
    cart = CheckoutCartLineSerializer(many=True)
    deliveryDetails = CheckoutDeliveryDetailsSerializer()
    paymentSelection = CheckoutPaymentSelectionSerializer()


class PickupLocationSerializer(serializers.ModelSerializer):
    streetAddress = serializers.CharField(source="street_address")
    contactName = serializers.CharField(source="contact_name", allow_blank=True)
    contactPhone = serializers.CharField(source="contact_phone")
    mapsUrl = serializers.CharField(source="maps_url")
    openingHours = serializers.CharField(source="opening_hours", allow_blank=True)
    collectionWindowHours = serializers.IntegerField(source="collection_window_hours")

    class Meta:
        model = PickupLocation
        fields = (
            "name",
            "county",
            "town",
            "streetAddress",
            "contactName",
            "contactPhone",
            "mapsUrl",
            "openingHours",
            "collectionWindowHours",
            "notes",
        )


class DeliverySettingsSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk", read_only=True)
    shopName = serializers.CharField(source="shop_name")
    shopCounty = serializers.CharField(source="shop_county")
    shopTown = serializers.CharField(source="shop_town")
    shopStreetAddress = serializers.CharField(source="shop_street_address")
    shopLatitude = serializers.FloatField(source="shop_latitude")
    shopLongitude = serializers.FloatField(source="shop_longitude")
    riderMaxRadiusKm = serializers.IntegerField(source="rider_max_radius_km")
    parcelSwitchRadiusKm = serializers.IntegerField(source="parcel_switch_radius_km")
    riderBaseFee = serializers.IntegerField(source="rider_base_fee")
    riderIncrementPer10Km = serializers.IntegerField(source="rider_increment_per_10km")
    riderEstimatedWindow = serializers.CharField(source="rider_estimated_window")
    parcelEstimatedWindow = serializers.CharField(source="parcel_estimated_window")
    allowPayOnDelivery = serializers.BooleanField(source="allow_pay_on_delivery")
    parcelManualFeeConfirmationRequired = serializers.BooleanField(
        source="parcel_manual_fee_confirmation_required"
    )
    isActive = serializers.BooleanField(source="is_active")

    class Meta:
        model = DeliverySettings
        fields = (
            "id",
            "name",
            "shopName",
            "shopCounty",
            "shopTown",
            "shopStreetAddress",
            "shopLatitude",
            "shopLongitude",
            "riderMaxRadiusKm",
            "parcelSwitchRadiusKm",
            "riderBaseFee",
            "riderIncrementPer10Km",
            "riderEstimatedWindow",
            "parcelEstimatedWindow",
            "allowPayOnDelivery",
            "parcelManualFeeConfirmationRequired",
            "isActive",
        )
