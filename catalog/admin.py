from django.contrib import admin

from catalog.models import Category, Product, ProductVariant
from common.admin_mixins import AttendantRestrictedFieldsMixin


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "external_id")
    search_fields = ("name", "slug", "external_id")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "category",
        "price",
        "badge",
        "is_featured",
        "is_new_arrival",
    )
    list_filter = ("category", "badge", "is_featured", "is_new_arrival")
    search_fields = ("name", "slug", "external_id", "description")
    inlines = [ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(AttendantRestrictedFieldsMixin, admin.ModelAdmin):
    list_display = ("product", "sku", "color", "size", "stock", "image_url")
    list_filter = ("color", "size")
    search_fields = ("sku", "external_id", "product__name")
    attendant_readonly_fields = (
        "external_id",
        "product",
        "size",
        "color",
        "color_hex",
        "image_url",
        "sku",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")
