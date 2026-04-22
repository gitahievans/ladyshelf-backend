from rest_framework import serializers

from checkout.models import PickupLocation


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
