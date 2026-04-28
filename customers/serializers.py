from rest_framework import serializers

from customers.models import Address, CustomerProfile


class AddressSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True, source="pk")
    fullName = serializers.CharField(source="full_name")
    streetAddress = serializers.CharField(source="street_address")
    additionalInfo = serializers.CharField(source="additional_info", allow_blank=True, required=False)
    isDefault = serializers.BooleanField(source="is_default")

    class Meta:
        model = Address
        fields = (
            "id",
            "label",
            "fullName",
            "phone",
            "county",
            "town",
            "streetAddress",
            "additionalInfo",
            "isDefault",
        )

    def create(self, validated_data):
        customer = self.context["customer"]
        if validated_data.get("is_default"):
            Address.objects.filter(customer=customer, is_default=True).update(is_default=False)

        return Address.objects.create(customer=customer, **validated_data)

    def update(self, instance, validated_data):
        if validated_data.get("is_default"):
            Address.objects.filter(customer=instance.customer, is_default=True).exclude(pk=instance.pk).update(
                is_default=False
            )

        return super().update(instance, validated_data)


class CustomerProfileSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="supabase_user_id")
    firstName = serializers.CharField(source="first_name")
    lastName = serializers.CharField(source="last_name")
    avatarUrl = serializers.CharField(source="avatar_url", allow_blank=True)
    createdAt = serializers.DateTimeField(source="created_at")
    addresses = AddressSerializer(many=True)

    class Meta:
        model = CustomerProfile
        fields = (
            "id",
            "email",
            "firstName",
            "lastName",
            "phone",
            "avatarUrl",
            "addresses",
            "createdAt",
        )


class CustomerProfileUpdateSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name", required=False)
    lastName = serializers.CharField(source="last_name", required=False)

    class Meta:
        model = CustomerProfile
        fields = ("firstName", "lastName", "phone")

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Please provide at least one field to update.")

        return attrs

    def validate_first_name(self, value):
        first_name = value.strip()
        if not first_name:
            raise serializers.ValidationError("Please provide your first name.")

        return first_name

    def validate_last_name(self, value):
        last_name = value.strip()
        if not last_name:
            raise serializers.ValidationError("Please provide your last name.")

        return last_name

    def validate_phone(self, value):
        phone = value.strip()
        if not phone:
            raise serializers.ValidationError("Please provide a phone number.")

        return phone
