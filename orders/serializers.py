from rest_framework import serializers

from orders.models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    productId = serializers.SerializerMethodField()
    variantId = serializers.CharField(source="variant_id")
    productName = serializers.CharField(source="product_name")
    productImage = serializers.CharField(source="product_image")
    colorHex = serializers.CharField(source="color_hex")

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "productId",
            "variantId",
            "quantity",
            "productName",
            "productImage",
            "price",
            "currency",
            "size",
            "color",
            "colorHex",
        )

    def get_productId(self, obj: OrderItem) -> str | None:
        return obj.product.external_id if obj.product else None


class OrderSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    orderNumber = serializers.CharField(source="order_number")
    userId = serializers.SerializerMethodField()
    guestEmail = serializers.CharField(source="guest_email", allow_blank=True)
    items = OrderItemSerializer(many=True)
    deliveryDetails = serializers.JSONField(source="delivery_details")
    deliveryFee = serializers.IntegerField(source="delivery_fee")
    deliveryMode = serializers.CharField(source="delivery_mode")
    paymentMethod = serializers.CharField(source="payment_method")
    paymentTiming = serializers.CharField(source="payment_timing")
    paymentStatus = serializers.CharField(source="payment_status")
    orderStatus = serializers.CharField(source="order_status")
    manualDeliveryFeeConfirmationRequired = serializers.BooleanField(
        source="manual_delivery_fee_confirmation_required"
    )
    pickupInstructions = serializers.JSONField(source="pickup_instructions", allow_null=True)
    paymentExpiresAt = serializers.DateTimeField(source="payment_expires_at", allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = Order
        fields = (
            "id",
            "orderNumber",
            "userId",
            "guestEmail",
            "items",
            "deliveryDetails",
            "subtotal",
            "deliveryFee",
            "discount",
            "total",
            "currency",
            "deliveryMode",
            "paymentMethod",
            "paymentTiming",
            "paymentStatus",
            "orderStatus",
            "manualDeliveryFeeConfirmationRequired",
            "pickupInstructions",
            "paymentExpiresAt",
            "createdAt",
            "updatedAt",
        )

    def get_userId(self, obj: Order) -> str | None:
        return obj.customer.supabase_user_id if obj.customer else None
