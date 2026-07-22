from django.contrib import admin

from admin_portal.models import (
    AdminStaffAccess,
    ImageGenerationBatch,
    ProductImageCandidate,
    ProductImageGeneration,
)


@admin.register(AdminStaffAccess)
class AdminStaffAccessAdmin(admin.ModelAdmin):
    list_display = ("customer", "role", "is_active", "created_at", "updated_at")
    list_filter = ("role", "is_active", "created_at")
    search_fields = ("customer__email", "customer__supabase_user_id")


class ProductImageCandidateInline(admin.TabularInline):
    model = ProductImageCandidate
    extra = 0
    readonly_fields = (
        "shot_type",
        "status",
        "prompt_policy_version",
        "regeneration_revision",
        "manual_overrides",
        "prompt",
        "seed",
        "storage_path",
        "public_url",
        "attempt_count",
        "last_error_code",
        "last_error_message",
        "reviewed_by",
        "reviewed_at",
    )


@admin.register(ImageGenerationBatch)
class ImageGenerationBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "product_count", "model", "requested_by", "created_at")
    list_filter = ("status", "provider", "created_at")
    readonly_fields = ("created_at", "updated_at", "completed_at")


@admin.register(ProductImageGeneration)
class ProductImageGenerationAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "status", "attempt_count", "created_at", "published_at")
    list_filter = ("status", "model", "created_at")
    search_fields = ("product__name", "product__slug")
    readonly_fields = ("source_snapshot", "previous_images", "created_at", "updated_at")
    inlines = [ProductImageCandidateInline]
