from django.contrib import admin

from wishlist.models import WishlistItem


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("customer", "product", "created_at")
    list_filter = ("created_at",)
    search_fields = ("customer__email", "product__name", "product__external_id")
