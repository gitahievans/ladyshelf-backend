from django.utils.text import slugify
from rest_framework import serializers

from admin_portal.access import build_permission_set
from admin_portal.models import AdminStaffAccess
from customers.serializers import AddressSerializer
from customers.models import CustomerProfile
from catalog.models import Category, Product, ProductVariant
from catalog.serializers import CategorySerializer, ProductSerializer, ProductVariantSerializer
from checkout.models import DeliverySettings, DeliveryZone, PickupLocation
from checkout.serializers import DeliverySettingsSerializer
from orders.models import Order
from orders.serializers import OrderItemSerializer, OrderSerializer
from payments.models import PaymentTransaction
from payments.serializers import PaymentTransactionSerializer, ReceiptSerializer
from wishlist.models import WishlistItem


class AdminStaffUserSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    supabaseUserId = serializers.CharField(source="customer.supabase_user_id")
    email = serializers.EmailField(source="customer.email")
    firstName = serializers.CharField(source="customer.first_name")
    lastName = serializers.CharField(source="customer.last_name")
    isActive = serializers.BooleanField(source="is_active")

    class Meta:
        model = AdminStaffAccess
        fields = (
            "id",
            "supabaseUserId",
            "email",
            "firstName",
            "lastName",
            "role",
            "isActive",
        )


class AdminStaffRecordSerializer(AdminStaffUserSerializer):
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")

    class Meta(AdminStaffUserSerializer.Meta):
        fields = (
            *AdminStaffUserSerializer.Meta.fields,
            "createdAt",
            "updatedAt",
        )


class AdminStaffCreateSerializer(serializers.Serializer):
    supabaseUserId = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=AdminStaffAccess.Role.choices)
    isActive = serializers.BooleanField(default=True)

    def validate(self, attrs):
        supabase_user_id = attrs.get("supabaseUserId", "").strip()
        email = attrs.get("email", "").strip()

        if not supabase_user_id and not email:
            raise serializers.ValidationError(
                "Provide either a Supabase user ID or email."
            )

        customer_query = CustomerProfile.objects.all()
        if supabase_user_id:
            customer_query = customer_query.filter(supabase_user_id=supabase_user_id)
        else:
            customer_query = customer_query.filter(email__iexact=email)

        customer = customer_query.first()
        if customer is None:
            raise serializers.ValidationError(
                "No customer profile was found for that staff identity."
            )

        if AdminStaffAccess.objects.filter(customer=customer).exists():
            raise serializers.ValidationError(
                "That user already has staff dashboard access."
            )

        attrs["customer"] = customer
        return attrs

    def create(self, validated_data):
        return AdminStaffAccess.objects.create(
            customer=validated_data["customer"],
            role=validated_data["role"],
            is_active=validated_data["isActive"],
        )


class AdminStaffUpdateSerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source="is_active", required=False)

    class Meta:
        model = AdminStaffAccess
        fields = ("role", "isActive")


class AdminDashboardOrderSerializer(serializers.Serializer):
    orderNumber = serializers.CharField()
    customerLabel = serializers.CharField(allow_blank=True)
    total = serializers.IntegerField()
    currency = serializers.CharField()
    paymentStatus = serializers.CharField()
    orderStatus = serializers.CharField()
    deliveryMode = serializers.CharField(allow_blank=True)
    createdAt = serializers.DateTimeField()


class AdminDashboardPaymentSerializer(serializers.Serializer):
    id = serializers.CharField()
    orderNumber = serializers.CharField()
    status = serializers.CharField()
    amount = serializers.IntegerField()
    currency = serializers.CharField()
    provider = serializers.CharField()
    createdAt = serializers.DateTimeField()


class AdminLowStockVariantSerializer(serializers.Serializer):
    id = serializers.CharField()
    productName = serializers.CharField()
    sku = serializers.CharField()
    size = serializers.CharField()
    color = serializers.CharField()
    stock = serializers.IntegerField()


class AdminDashboardSummarySerializer(serializers.Serializer):
    awaitingPaymentOrders = serializers.IntegerField()
    fulfillmentActionOrders = serializers.IntegerField()
    lowStockVariants = serializers.IntegerField()
    recentPaidOrders = AdminDashboardOrderSerializer(many=True)
    paymentIssueCount = serializers.IntegerField()
    paymentIssues = AdminDashboardPaymentSerializer(many=True)
    lowStockItems = AdminLowStockVariantSerializer(many=True)


class AdminOrderListItemSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    orderNumber = serializers.CharField(source="order_number")
    customerLabel = serializers.SerializerMethodField()
    deliveryMode = serializers.CharField(source="delivery_mode")
    paymentMethod = serializers.CharField(source="payment_method")
    paymentTiming = serializers.CharField(source="payment_timing")
    paymentStatus = serializers.CharField(source="payment_status")
    orderStatus = serializers.CharField(source="order_status")
    manualDeliveryFeeConfirmationRequired = serializers.BooleanField(
        source="manual_delivery_fee_confirmation_required"
    )
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = Order
        fields = (
            "id",
            "orderNumber",
            "customerLabel",
            "total",
            "currency",
            "deliveryMode",
            "paymentMethod",
            "paymentTiming",
            "paymentStatus",
            "orderStatus",
            "manualDeliveryFeeConfirmationRequired",
            "createdAt",
            "updatedAt",
        )

    def get_customerLabel(self, obj: Order) -> str:
        if obj.customer:
            return obj.customer.email

        return obj.guest_email


class AdminOrderDetailSerializer(OrderSerializer):
    internalNotes = serializers.CharField(source="internal_notes", allow_blank=True)
    paymentTransactions = PaymentTransactionSerializer(
        many=True,
        read_only=True,
        source="payment_transactions",
    )
    receipt = ReceiptSerializer(read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = (
            *OrderSerializer.Meta.fields,
            "internalNotes",
            "paymentTransactions",
            "receipt",
        )


class AdminOrderUpdateSerializer(serializers.ModelSerializer):
    orderStatus = serializers.ChoiceField(
        choices=Order.OrderStatus.choices,
        source="order_status",
        required=False,
    )
    paymentStatus = serializers.ChoiceField(
        choices=Order.PaymentStatus.choices,
        source="payment_status",
        required=False,
    )
    internalNotes = serializers.CharField(
        source="internal_notes",
        allow_blank=True,
        required=False,
    )

    class Meta:
        model = Order
        fields = ("orderStatus", "paymentStatus", "internalNotes")


class AdminManualPaymentSerializer(serializers.Serializer):
    amountCollected = serializers.IntegerField(required=False, min_value=1)
    paymentMethod = serializers.ChoiceField(
        choices=Order.PaymentMethod.choices,
        default=Order.PaymentMethod.MPESA,
    )
    paymentReference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    staffNote = serializers.CharField(required=False, allow_blank=True)


class AdminPaymentListItemSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    orderNumber = serializers.CharField(source="order.order_number")
    paymentMethod = serializers.CharField(source="payment_method")
    merchantReference = serializers.CharField(source="merchant_reference")
    transactionCode = serializers.CharField(source="transaction_code")
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = PaymentTransaction
        fields = (
            "id",
            "orderNumber",
            "provider",
            "status",
            "paymentMethod",
            "amount",
            "currency",
            "merchantReference",
            "transactionCode",
            "createdAt",
            "updatedAt",
        )


class AdminPaymentDetailSerializer(PaymentTransactionSerializer):
    id = serializers.CharField(source="pk")
    orderNumber = serializers.CharField(source="order.order_number")

    class Meta(PaymentTransactionSerializer.Meta):
        fields = (
            "id",
            "orderNumber",
            *PaymentTransactionSerializer.Meta.fields,
        )


class AdminCustomerListItemSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    supabaseUserId = serializers.CharField(source="supabase_user_id")
    firstName = serializers.CharField(source="first_name")
    lastName = serializers.CharField(source="last_name")
    orderCount = serializers.IntegerField()
    createdAt = serializers.DateTimeField(source="created_at")

    class Meta:
        model = CustomerProfile
        fields = (
            "id",
            "supabaseUserId",
            "email",
            "firstName",
            "lastName",
            "phone",
            "orderCount",
            "createdAt",
        )


class AdminWishlistProductSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    slug = serializers.CharField()


class AdminCustomerDetailSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    supabaseUserId = serializers.CharField(source="supabase_user_id")
    firstName = serializers.CharField(source="first_name")
    lastName = serializers.CharField(source="last_name")
    avatarUrl = serializers.CharField(source="avatar_url", allow_blank=True)
    emailConfirmedAt = serializers.DateTimeField(source="email_confirmed_at", allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")
    addresses = AddressSerializer(many=True)
    recentOrders = serializers.SerializerMethodField()
    wishlist = serializers.SerializerMethodField()

    class Meta:
        model = CustomerProfile
        fields = (
            "id",
            "supabaseUserId",
            "email",
            "firstName",
            "lastName",
            "phone",
            "avatarUrl",
            "emailConfirmedAt",
            "createdAt",
            "updatedAt",
            "addresses",
            "recentOrders",
            "wishlist",
        )

    def get_recentOrders(self, obj: CustomerProfile):
        orders = obj.orders.all()[:8]
        return AdminOrderListItemSerializer(orders, many=True).data

    def get_wishlist(self, obj: CustomerProfile):
        wishlist_items = WishlistItem.objects.select_related("product").filter(customer=obj)[:8]
        return [
            {
                "id": item.product.external_id,
                "name": item.product.name,
                "slug": item.product.slug,
            }
            for item in wishlist_items
        ]


class AdminCategoryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("external_id", "slug", "name", "description", "image")


def generate_unique_external_id(*, base_value: str, prefix: str, model_class) -> str:
    base_slug = slugify(base_value)[:40].strip("-") or prefix
    candidate = f"{prefix}-{base_slug}"[:50]
    suffix = 2

    while model_class.objects.filter(external_id=candidate).exists():
        suffix_text = f"-{suffix}"
        trimmed_base = base_slug[: max(1, 50 - len(prefix) - len(suffix_text) - 1)]
        candidate = f"{prefix}-{trimmed_base}{suffix_text}"
        suffix += 1

    return candidate


class AdminProductWriteSerializer(serializers.ModelSerializer):
    categorySlug = serializers.SlugRelatedField(
        queryset=Category.objects.all(),
        slug_field="slug",
        source="category",
    )
    originalPrice = serializers.IntegerField(
        source="original_price",
        allow_null=True,
        required=False,
    )
    isFeatured = serializers.BooleanField(source="is_featured", required=False)
    isNewArrival = serializers.BooleanField(source="is_new_arrival", required=False)
    careInstructions = serializers.CharField(
        source="care_instructions",
        allow_blank=True,
        required=False,
    )
    external_id = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = (
            "external_id",
            "slug",
            "name",
            "brand",
            "categorySlug",
            "description",
            "images",
            "price",
            "originalPrice",
            "currency",
            "badge",
            "tags",
            "rating",
            "review_count",
            "isFeatured",
            "isNewArrival",
            "material",
            "careInstructions",
            "created_at",
        )

    def create(self, validated_data):
        external_id = (validated_data.get("external_id") or "").strip()
        if not external_id:
            validated_data["external_id"] = generate_unique_external_id(
                base_value=validated_data.get("name", ""),
                prefix="prod",
                model_class=Product,
            )

        return super().create(validated_data)


class AdminVariantWriteSerializer(serializers.ModelSerializer):
    colorHex = serializers.CharField(source="color_hex")
    imageUrl = serializers.URLField(source="image_url", required=False, allow_blank=True)
    external_id = serializers.CharField(required=False, allow_blank=True)
    sku = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = ProductVariant
        fields = ("external_id", "size", "color", "colorHex", "imageUrl", "stock", "sku")

    def create(self, validated_data):
        sku = (validated_data.get("sku") or "").strip()
        if not sku:
            product = validated_data.get("product")
            product_slug = product.slug if product else "item"
            color = slugify(validated_data.get("color", ""))[:12] or "default"
            size = slugify(validated_data.get("size", ""))[:12] or "size"
            base_sku = f"{product_slug}-{color}-{size}".upper().replace("-", "-")
            candidate = base_sku[:50]
            suffix = 2

            while ProductVariant.objects.filter(sku=candidate).exists():
                suffix_text = f"-{suffix}"
                trimmed_base = base_sku[: max(1, 50 - len(suffix_text))]
                candidate = f"{trimmed_base}{suffix_text}"
                suffix += 1

            validated_data["sku"] = candidate

        external_id = (validated_data.get("external_id") or "").strip()
        if not external_id:
            product = validated_data.get("product")
            parts = [
                product.slug if product else "",
                validated_data.get("sku", ""),
                validated_data.get("color", ""),
                validated_data.get("size", ""),
            ]
            validated_data["external_id"] = generate_unique_external_id(
                base_value="-".join(filter(None, parts)),
                prefix="variant",
                model_class=ProductVariant,
            )

        return super().create(validated_data)


class AdminInventoryRowSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    externalId = serializers.CharField(source="external_id")
    productName = serializers.CharField(source="product.name")
    productSlug = serializers.CharField(source="product.slug")
    colorHex = serializers.CharField(source="color_hex")
    imageUrl = serializers.CharField(source="image_url", allow_blank=True)

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "externalId",
            "productName",
            "productSlug",
            "size",
            "color",
            "colorHex",
            "imageUrl",
            "stock",
            "sku",
        )


class AdminStockUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ("stock",)


class AdminDeliveryZoneSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk", read_only=True)
    deliveryMode = serializers.CharField(source="delivery_mode")
    deliveryFee = serializers.IntegerField(source="delivery_fee")
    manualFeeConfirmationRequired = serializers.BooleanField(source="manual_fee_confirmation_required")
    allowPayOnDelivery = serializers.BooleanField(source="allow_pay_on_delivery")
    estimatedWindow = serializers.CharField(source="estimated_window", allow_blank=True, required=False)
    isActive = serializers.BooleanField(source="is_active")

    class Meta:
        model = DeliveryZone
        fields = (
            "id",
            "name",
            "deliveryMode",
            "counties",
            "towns",
            "deliveryFee",
            "manualFeeConfirmationRequired",
            "allowPayOnDelivery",
            "estimatedWindow",
            "priority",
            "isActive",
        )


class AdminDeliverySettingsSerializer(DeliverySettingsSerializer):
    class Meta(DeliverySettingsSerializer.Meta):
        fields = DeliverySettingsSerializer.Meta.fields


class AdminPickupLocationSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk", read_only=True)
    streetAddress = serializers.CharField(source="street_address")
    contactName = serializers.CharField(source="contact_name", allow_blank=True, required=False)
    contactPhone = serializers.CharField(source="contact_phone")
    mapsUrl = serializers.CharField(source="maps_url")
    openingHours = serializers.CharField(source="opening_hours", allow_blank=True, required=False)
    collectionWindowHours = serializers.IntegerField(source="collection_window_hours")
    isActive = serializers.BooleanField(source="is_active")

    class Meta:
        model = PickupLocation
        fields = (
            "id",
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
            "isActive",
        )


class AdminPermissionSetSerializer(serializers.Serializer):
    dashboard = serializers.BooleanField()
    orders = serializers.DictField(child=serializers.BooleanField())
    payments = serializers.DictField(child=serializers.BooleanField())
    customers = serializers.DictField(child=serializers.BooleanField())
    catalog = serializers.DictField(child=serializers.BooleanField())
    inventory = serializers.DictField(child=serializers.BooleanField())
    settings = serializers.DictField(child=serializers.BooleanField())
    staff = serializers.DictField(child=serializers.BooleanField())


def serialize_permission_set(staff_access: AdminStaffAccess) -> dict[str, object]:
    permission_set = build_permission_set(staff_access.role)
    serializer = AdminPermissionSetSerializer(data=permission_set)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data
