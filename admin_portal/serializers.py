import re
import unicodedata

from django.utils.text import slugify
from rest_framework import serializers

from admin_portal.access import build_permission_set
from admin_portal.models import (
    AdminStaffAccess,
    ImageGenerationBatch,
    ProductImageCandidate,
    ProductImageGeneration,
)
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
    isPublished = serializers.BooleanField(source="is_published", required=False)
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
            "isPublished",
            "material",
            "careInstructions",
            "created_at",
        )

    def validate(self, attrs):
        instance_images = self.instance.images if self.instance else []
        images = attrs.get("images", instance_images)
        is_published = attrs.get(
            "is_published",
            self.instance.is_published if self.instance else False,
        )
        if is_published and not images:
            raise serializers.ValidationError(
                {"isPublished": "Add at least one product image before publishing."}
            )
        return attrs

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


class ImageGenerationBatchCreateSerializer(serializers.Serializer):
    productIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=5,
        allow_empty=False,
    )

    def validate_productIds(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Select each product only once.")
        return value


class ImageGenerationPublishSerializer(serializers.Serializer):
    publicationMode = serializers.ChoiceField(
        choices=ProductImageGeneration.PublicationMode.values,
    )


BODY_PROFILE_CHOICES = ("automatic", "slim", "curvy", "athletic")
SKIN_TONE_CHOICES = ("automatic", "light_brown", "medium_brown", "deep_brown")
COMPOSITION_CHOICES = ("automatic", "standing", "seated", "walking", "three_quarter")
DETAIL_FOCUS_CHOICES = ("automatic", "fabric", "pattern", "stitching", "closure", "construction")
KNOWN_COLOR_WORDS = {
    "black", "blue", "brown", "cream", "gold", "gray", "green", "grey", "ivory",
    "maroon", "navy", "orange", "pink", "purple", "red", "silver", "tan", "teal",
    "white", "yellow",
}
PROHIBITED_NOTE_PATTERNS = (
    (r"\b(?:man|men|male|males|boy|boys|child|children|kid|kids|teen(?:ager)?s?|girl|girls|minor|non[- ]adult)\b", "Models must be adult Black women."),
    (r"\b(?:(?:white|asian|caucasian|non[- ]?black)\s+(?:model|woman|person)|not\s+black)\b", "Models must be Black women."),
    (r"\b(?:nude|nudity|naked|explicit|sexual|fetish)\b", "Unsafe or sexualized direction is not allowed."),
    (
        r"\b(?:add|remove|replace|redesign|change|alter)\b.{0,40}\b(?:sleeve|collar|neckline|hem|closure|zipper|button|print|pattern|fabric|material|design)\b",
        "Instructions cannot change the product design.",
    ),
    (r"\b(?:sleeveless|backless)\b", "Instructions cannot change the product design."),
)


def normalize_regeneration_instruction(value: str) -> str:
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise serializers.ValidationError("Control characters are not allowed.")
    normalized = " ".join(value.split())
    lowered = normalized.lower()
    for pattern, message in PROHIBITED_NOTE_PATTERNS:
        if re.search(pattern, lowered):
            raise serializers.ValidationError(message)
    return normalized


class ModelShotRegenerationSerializer(serializers.Serializer):
    color = serializers.CharField(required=False, allow_null=True, allow_blank=False, max_length=120)
    bodyProfile = serializers.ChoiceField(choices=BODY_PROFILE_CHOICES, default="automatic")
    skinTone = serializers.ChoiceField(choices=SKIN_TONE_CHOICES, default="automatic")
    composition = serializers.ChoiceField(choices=COMPOSITION_CHOICES, default="automatic")
    instruction = serializers.CharField(required=False, allow_blank=True, max_length=500, default="", trim_whitespace=False)

    def validate_instruction(self, value):
        return normalize_regeneration_instruction(value)


class DetailShotRegenerationSerializer(serializers.Serializer):
    color = serializers.CharField(required=False, allow_null=True, allow_blank=False, max_length=120)
    detailFocus = serializers.ChoiceField(choices=DETAIL_FOCUS_CHOICES, default="automatic")
    instruction = serializers.CharField(required=False, allow_blank=True, max_length=500, default="", trim_whitespace=False)

    def validate_instruction(self, value):
        return normalize_regeneration_instruction(value)


class CandidateRegenerationSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("shot", "set"))
    shots = serializers.DictField(allow_empty=False)

    def validate(self, attrs):
        candidate = self.context["candidate"]
        scope = attrs["scope"]
        raw_shots = attrs["shots"]
        if candidate.shot_type == ProductImageCandidate.ShotType.HERO and scope != "set":
            raise serializers.ValidationError({"scope": "Hero regeneration requires full-set scope."})
        if candidate.shot_type != ProductImageCandidate.ShotType.HERO and scope != "shot":
            raise serializers.ValidationError({"scope": "Alternate and Detail regeneration require shot scope."})

        expected_shots = (
            {choice for choice, _label in ProductImageCandidate.ShotType.choices}
            if scope == "set"
            else {candidate.shot_type}
        )
        received_shots = set(raw_shots)
        if received_shots != expected_shots:
            missing = sorted(expected_shots - received_shots)
            unexpected = sorted(received_shots - expected_shots)
            errors = []
            if missing:
                errors.append(f"Missing shot settings: {', '.join(missing)}.")
            if unexpected:
                errors.append(f"Unexpected shot settings: {', '.join(unexpected)}.")
            raise serializers.ValidationError({"shots": errors})

        catalog_colors = [str(color) for color in candidate.generation.source_snapshot.get("colors", [])]
        colors_by_key = {color.casefold(): color for color in catalog_colors}
        normalized_shots = {}
        shot_errors = {}
        for shot_type in expected_shots:
            shot_serializer_class = (
                DetailShotRegenerationSerializer
                if shot_type == ProductImageCandidate.ShotType.DETAIL
                else ModelShotRegenerationSerializer
            )
            shot_serializer = shot_serializer_class(data=raw_shots[shot_type])
            if not shot_serializer.is_valid():
                shot_errors[shot_type] = shot_serializer.errors
                continue
            shot_data = dict(shot_serializer.validated_data)
            selected_color = shot_data.get("color")
            if selected_color is not None:
                canonical_color = colors_by_key.get(selected_color.strip().casefold())
                if canonical_color is None:
                    shot_errors.setdefault(shot_type, {})["color"] = [
                        "Select a color from the frozen catalog snapshot."
                    ]
                else:
                    shot_data["color"] = canonical_color
            instruction = shot_data.get("instruction", "")
            color_match = re.search(
                r"\b(?:use|make|paint|recolor|colour|color|in)\s+(?:the\s+product\s+)?(?:to\s+)?(" + "|".join(sorted(KNOWN_COLOR_WORDS)) + r")\b",
                instruction.lower(),
            )
            if color_match and color_match.group(1).casefold() not in colors_by_key:
                shot_errors.setdefault(shot_type, {})["instruction"] = [
                    "Instructions cannot request a color outside the frozen catalog snapshot."
                ]
            normalized_shots[shot_type] = shot_data
        if shot_errors:
            raise serializers.ValidationError({"shots": shot_errors})

        if len(catalog_colors) >= 3:
            explicit_colors = [
                values["color"] for values in normalized_shots.values() if values.get("color")
            ]
            unchanged_colors = [
                other.manual_overrides.get("resolved", {}).get("color")
                for other in candidate.generation.candidates.all()
                if other.shot_type not in expected_shots
            ]
            all_selected = explicit_colors + [color for color in unchanged_colors if color]
            if len(all_selected) != len(set(all_selected)):
                raise serializers.ValidationError(
                    {"shots": "Choose different explicit colors while three or more catalog colors are available."}
                )

        attrs["shots"] = normalized_shots
        return attrs


class ProductImageCandidateSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    shotType = serializers.CharField(source="shot_type")
    publicUrl = serializers.SerializerMethodField()
    mimeType = serializers.CharField(source="mime_type")
    attemptCount = serializers.IntegerField(source="attempt_count")
    errorCode = serializers.CharField(source="last_error_code")
    errorMessage = serializers.CharField(source="last_error_message")
    reviewedAt = serializers.DateTimeField(source="reviewed_at", allow_null=True)
    promptPolicyVersion = serializers.CharField(source="prompt_policy_version")
    regenerationRevision = serializers.IntegerField(source="regeneration_revision")
    manualOverrides = serializers.JSONField(source="manual_overrides")

    class Meta:
        model = ProductImageCandidate
        fields = (
            "id",
            "shotType",
            "status",
            "prompt",
            "promptPolicyVersion",
            "regenerationRevision",
            "manualOverrides",
            "publicUrl",
            "mimeType",
            "width",
            "height",
            "attemptCount",
            "errorCode",
            "errorMessage",
            "reviewedAt",
        )

    def get_publicUrl(self, obj: ProductImageCandidate) -> str:
        if obj.status in {
            ProductImageCandidate.Status.READY,
            ProductImageCandidate.Status.APPROVED,
        }:
            separator = "&" if "?" in obj.public_url else "?"
            return f"{obj.public_url}{separator}v={obj.regeneration_revision}"
        return ""


class ProductImageGenerationSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    productId = serializers.CharField(source="product.pk")
    productName = serializers.CharField(source="product.name")
    productSlug = serializers.CharField(source="product.slug")
    attemptCount = serializers.IntegerField(source="attempt_count")
    nextAttemptAt = serializers.DateTimeField(source="next_attempt_at", allow_null=True)
    errorCode = serializers.CharField(source="last_error_code")
    errorMessage = serializers.CharField(source="last_error_message")
    previousImages = serializers.JSONField(source="previous_images")
    publicationMode = serializers.CharField(source="publication_mode", allow_null=True)
    currentGalleryCount = serializers.SerializerMethodField()
    canPublish = serializers.SerializerMethodField()
    canRestore = serializers.SerializerMethodField()
    candidates = ProductImageCandidateSerializer(many=True)
    catalogColors = serializers.SerializerMethodField()

    class Meta:
        model = ProductImageGeneration
        fields = (
            "id",
            "productId",
            "productName",
            "productSlug",
            "status",
            "model",
            "attemptCount",
            "nextAttemptAt",
            "errorCode",
            "errorMessage",
            "previousImages",
            "publicationMode",
            "currentGalleryCount",
            "catalogColors",
            "canPublish",
            "canRestore",
            "candidates",
            "created_at",
            "updated_at",
            "published_at",
        )

    def get_canPublish(self, obj: ProductImageGeneration) -> bool:
        candidates = list(obj.candidates.all())
        return len(candidates) == 3 and all(
            candidate.status == ProductImageCandidate.Status.APPROVED
            for candidate in candidates
        )

    def get_canRestore(self, obj: ProductImageGeneration) -> bool:
        return obj.status == ProductImageGeneration.Status.PUBLISHED

    def get_currentGalleryCount(self, obj: ProductImageGeneration) -> int:
        return len(obj.product.images)

    def get_catalogColors(self, obj: ProductImageGeneration) -> list[str]:
        return list(obj.source_snapshot.get("colors", []))


class ImageGenerationBatchSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="pk")
    productCount = serializers.IntegerField(source="product_count")
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")
    completedAt = serializers.DateTimeField(source="completed_at", allow_null=True)
    generations = ProductImageGenerationSerializer(many=True)

    class Meta:
        model = ImageGenerationBatch
        fields = (
            "id",
            "status",
            "provider",
            "model",
            "productCount",
            "generations",
            "createdAt",
            "updatedAt",
            "completedAt",
        )


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
