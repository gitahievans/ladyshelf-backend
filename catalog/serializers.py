from django.db.models import Count
from rest_framework import serializers

from catalog.models import Category, Product, ProductVariant


class ProductVariantSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="external_id")
    adminId = serializers.CharField(source="pk")
    colorHex = serializers.CharField(source="color_hex")
    imageUrl = serializers.CharField(source="image_url", allow_blank=True)

    class Meta:
        model = ProductVariant
        fields = ("id", "adminId", "size", "color", "colorHex", "imageUrl", "stock", "sku")


class ProductSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="external_id")
    adminId = serializers.CharField(source="pk")
    categorySlug = serializers.CharField(source="category.slug")
    originalPrice = serializers.IntegerField(source="original_price", allow_null=True)
    reviewCount = serializers.IntegerField(source="review_count")
    isFeatured = serializers.BooleanField(source="is_featured")
    isNewArrival = serializers.BooleanField(source="is_new_arrival")
    material = serializers.CharField(allow_blank=True)
    careInstructions = serializers.CharField(source="care_instructions", allow_blank=True)
    createdAt = serializers.DateTimeField(source="created_at")
    variants = ProductVariantSerializer(many=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "adminId",
            "slug",
            "name",
            "brand",
            "categorySlug",
            "description",
            "images",
            "variants",
            "price",
            "originalPrice",
            "currency",
            "badge",
            "tags",
            "rating",
            "reviewCount",
            "isFeatured",
            "isNewArrival",
            "material",
            "careInstructions",
            "createdAt",
        )


class CategorySerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="external_id")
    productCount = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "slug", "name", "description", "image", "productCount")

    def get_productCount(self, obj: Category) -> int:
        annotated_count = getattr(obj, "product_count", None)

        if annotated_count is not None:
            return annotated_count

        return obj.products.aggregate(product_count=Count("id"))["product_count"] or 0
