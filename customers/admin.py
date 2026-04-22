from django.contrib import admin

from customers.models import Address, CustomerProfile


class AddressInline(admin.TabularInline):
    extra = 0
    model = Address


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    inlines = [AddressInline]
    list_display = ("email", "first_name", "last_name", "phone", "created_at")
    search_fields = ("email", "first_name", "last_name", "supabase_user_id")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("full_name", "label", "town", "county", "is_default")
    list_filter = ("label", "county", "is_default")
    search_fields = ("full_name", "phone", "town", "county")

# Register your models here.
