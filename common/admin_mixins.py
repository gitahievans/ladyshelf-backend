from __future__ import annotations

from django.contrib import admin

from common.admin_roles import is_attendant, is_owner


class ReadOnlyInlineMixin:
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AttendantRestrictedFieldsMixin(admin.ModelAdmin):
    attendant_readonly_fields: tuple[str, ...] = ()

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))

        if is_attendant(request.user) and not is_owner(request.user):
            readonly_fields.extend(self.attendant_readonly_fields)

        return tuple(dict.fromkeys(readonly_fields))
