from __future__ import annotations

from admin_portal.models import AdminStaffAccess

PermissionValue = dict[str, bool] | bool
PermissionSet = dict[str, PermissionValue]


def get_staff_access(user) -> AdminStaffAccess | None:
    if not getattr(user, "is_authenticated", False):
        return None

    try:
        staff_access = user.admin_staff_access
    except AdminStaffAccess.DoesNotExist:
        return None

    if not staff_access.is_active:
        return None

    return staff_access


def build_permission_set(role: str) -> PermissionSet:
    owner_permissions: PermissionSet = {
        "dashboard": True,
        "orders": {"view": True, "manage": True},
        "payments": {"view": True, "manage": True},
        "customers": {"view": True, "manage": True},
        "catalog": {"view": True, "manage": True},
        "inventory": {"view": True, "manage": True},
        "settings": {"view": True, "manage": True},
        "staff": {"view": True, "manage": True},
    }
    attendant_permissions: PermissionSet = {
        "dashboard": True,
        "orders": {"view": True, "manage": True},
        "payments": {"view": True, "manage": False},
        "customers": {"view": True, "manage": False},
        "catalog": {"view": True, "manage": False},
        "inventory": {"view": True, "manage": True},
        "settings": {"view": False, "manage": False},
        "staff": {"view": False, "manage": False},
    }

    if role == AdminStaffAccess.Role.OWNER:
        return owner_permissions

    return attendant_permissions
