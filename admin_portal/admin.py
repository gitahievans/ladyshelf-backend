from django.contrib import admin

from admin_portal.models import AdminStaffAccess


@admin.register(AdminStaffAccess)
class AdminStaffAccessAdmin(admin.ModelAdmin):
    list_display = ("customer", "role", "is_active", "created_at", "updated_at")
    list_filter = ("role", "is_active", "created_at")
    search_fields = ("customer__email", "customer__supabase_user_id")

