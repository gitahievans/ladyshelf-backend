from rest_framework import serializers

from orders.models import Order, OrderCancellation, OrderCancellationItem, OrderItem
from orders.services import can_cancel_order, get_order_cancellation_unavailable_reason


class OrderItemSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    productId = serializers.SerializerMethodField()
    variantId = serializers.CharField(source="variant_id")
    productName = serializers.CharField(source="product_name")
    productImage = serializers.CharField(source="product_image")
    colorHex = serializers.CharField(source="color_hex")
    cancelledQuantity = serializers.IntegerField(source="cancelled_quantity")
    cancellableQuantity = serializers.SerializerMethodField()
    isFullyCancelled = serializers.SerializerMethodField()

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
            "cancelledQuantity",
            "cancellableQuantity",
            "isFullyCancelled",
        )

    def get_productId(self, obj: OrderItem) -> str | None:
        return obj.product.external_id if obj.product else None

    def get_cancellableQuantity(self, obj: OrderItem) -> int:
        return max(obj.quantity - obj.cancelled_quantity, 0)

    def get_isFullyCancelled(self, obj: OrderItem) -> bool:
        return obj.cancelled_quantity >= obj.quantity


class OrderCancellationItemSerializer(serializers.ModelSerializer):
    orderItemId = serializers.CharField(source="order_item.pk")
    productName = serializers.CharField(source="order_item.product_name")
    unitPrice = serializers.IntegerField(source="unit_price")
    lineTotal = serializers.IntegerField(source="line_total")

    class Meta:
        model = OrderCancellationItem
        fields = (
            "orderItemId",
            "productName",
            "quantity",
            "unitPrice",
            "lineTotal",
        )


class OrderCancellationSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    reasonLabel = serializers.CharField(source="get_reason_display")
    createdAt = serializers.DateTimeField(source="created_at")
    items = OrderCancellationItemSerializer(many=True)

    class Meta:
        model = OrderCancellation
        fields = (
            "id",
            "source",
            "reason",
            "reasonLabel",
            "note",
            "items",
            "createdAt",
        )


class OrderCancellationLineInputSerializer(serializers.Serializer):
    orderItemId = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class OrderCancellationCreateSerializer(serializers.Serializer):
    items = OrderCancellationLineInputSerializer(many=True, allow_empty=False)
    reason = serializers.ChoiceField(choices=OrderCancellation.Reason.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


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
    canCancel = serializers.SerializerMethodField()
    cancellationUnavailableReason = serializers.SerializerMethodField()
    cancellations = OrderCancellationSerializer(many=True, read_only=True)
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
            "canCancel",
            "cancellationUnavailableReason",
            "cancellations",
            "createdAt",
            "updatedAt",
        )

    def get_userId(self, obj: Order) -> str | None:
        return obj.customer.supabase_user_id if obj.customer else None

    def get_canCancel(self, obj: Order) -> bool:
        return can_cancel_order(obj)

    def get_cancellationUnavailableReason(self, obj: Order) -> str:
        return get_order_cancellation_unavailable_reason(obj)
