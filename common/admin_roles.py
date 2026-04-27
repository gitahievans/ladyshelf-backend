from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import Group, Permission

OWNER_GROUP_NAME = "Owner"
ATTENDANT_GROUP_NAME = "Attendant"


@dataclass(frozen=True)
class RolePermissionSpec:
    app_label: str
    model_name: str
    actions: tuple[str, ...]


OWNER_PERMISSION_SPECS = (
    RolePermissionSpec("catalog", "category", ("view", "add", "change", "delete")),
    RolePermissionSpec("catalog", "product", ("view", "add", "change", "delete")),
    RolePermissionSpec("catalog", "productvariant", ("view", "add", "change", "delete")),
    RolePermissionSpec("checkout", "deliverysettings", ("view", "add", "change", "delete")),
    RolePermissionSpec("checkout", "deliveryzone", ("view", "add", "change", "delete")),
    RolePermissionSpec("checkout", "pickuplocation", ("view", "add", "change", "delete")),
    RolePermissionSpec("customers", "customerprofile", ("view", "add", "change", "delete")),
    RolePermissionSpec("customers", "address", ("view", "add", "change", "delete")),
    RolePermissionSpec("wishlist", "wishlistitem", ("view", "add", "change", "delete")),
    RolePermissionSpec("orders", "order", ("view", "add", "change", "delete")),
    RolePermissionSpec("orders", "orderitem", ("view", "add", "change", "delete")),
    RolePermissionSpec("payments", "paymenttransaction", ("view", "add", "change", "delete")),
)

ATTENDANT_PERMISSION_SPECS = (
    RolePermissionSpec("catalog", "category", ("view",)),
    RolePermissionSpec("catalog", "product", ("view",)),
    RolePermissionSpec("catalog", "productvariant", ("view", "change")),
    RolePermissionSpec("checkout", "deliverysettings", ("view",)),
    RolePermissionSpec("checkout", "deliveryzone", ("view",)),
    RolePermissionSpec("checkout", "pickuplocation", ("view",)),
    RolePermissionSpec("customers", "customerprofile", ("view",)),
    RolePermissionSpec("customers", "address", ("view",)),
    RolePermissionSpec("wishlist", "wishlistitem", ("view",)),
    RolePermissionSpec("orders", "order", ("view", "change")),
    RolePermissionSpec("orders", "orderitem", ("view",)),
    RolePermissionSpec("payments", "paymenttransaction", ("view",)),
)


def _permission_codenames(specs: tuple[RolePermissionSpec, ...]) -> list[str]:
    return [
        f"{action}_{spec.model_name}"
        for spec in specs
        for action in spec.actions
    ]


def _permissions_for_specs(specs: tuple[RolePermissionSpec, ...]):
    permission_codenames = _permission_codenames(specs)
    return Permission.objects.filter(codename__in=permission_codenames)


def bootstrap_admin_groups() -> dict[str, int]:
    owner_group, _ = Group.objects.get_or_create(name=OWNER_GROUP_NAME)
    attendant_group, _ = Group.objects.get_or_create(name=ATTENDANT_GROUP_NAME)

    owner_permissions = _permissions_for_specs(OWNER_PERMISSION_SPECS)
    attendant_permissions = _permissions_for_specs(ATTENDANT_PERMISSION_SPECS)

    owner_group.permissions.set(owner_permissions)
    attendant_group.permissions.set(attendant_permissions)

    return {
        OWNER_GROUP_NAME: owner_permissions.count(),
        ATTENDANT_GROUP_NAME: attendant_permissions.count(),
    }


def is_owner(user) -> bool:
    if not getattr(user, "is_active", False):
        return False

    return getattr(user, "is_superuser", False) or user.groups.filter(
        name=OWNER_GROUP_NAME
    ).exists()


def is_attendant(user) -> bool:
    if not getattr(user, "is_active", False):
        return False

    return user.groups.filter(name=ATTENDANT_GROUP_NAME).exists()
