from rest_framework.permissions import BasePermission

from admin_portal.access import get_staff_access
from admin_portal.models import AdminStaffAccess


class IsAdminStaff(BasePermission):
    message = "You do not have staff access to this dashboard."

    def has_permission(self, request, view) -> bool:
        return get_staff_access(request.user) is not None


class IsAdminOwner(BasePermission):
    message = "Only owners can perform this action."

    def has_permission(self, request, view) -> bool:
        staff_access = get_staff_access(request.user)

        return bool(staff_access and staff_access.role == AdminStaffAccess.Role.OWNER)

