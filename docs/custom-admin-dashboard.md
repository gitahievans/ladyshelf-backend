# Custom Admin Dashboard Runbook

The custom dashboard and Django admin intentionally coexist.

Use the custom dashboard for day-to-day staff workflows. Keep Django admin available for emergency access, deeper model inspection, bulk maintenance, superuser tasks, and any workflow that has not yet been polished in the custom UI.

## Access model

- Staff dashboard identity is based on Supabase-authenticated customer profiles.
- Dashboard access is granted through `AdminStaffAccess`.
- `owner` users can manage staff access, catalog records, delivery zones, pickup locations, orders, payments, customers, and inventory.
- `attendant` users can view operational records and update stock through the inventory workflow.
- Deactivating a staff record removes dashboard access on the next admin request.

## Daily workflows

- Dashboard home: use `/admin` for operational counts, payment attention, low-stock alerts, and quick links.
- Staff management: owners use `/admin/staff` to add, activate, deactivate, or change staff roles.
- Orders: use `/admin/orders` to search, filter, open order details, update order status, update payment status, and maintain internal notes.
- Payments: use `/admin/payments` to inspect SasaPay transaction state and raw provider payloads.
- Customers: use `/admin/customers` to search profiles and inspect addresses, recent orders, and wishlist context.
- Catalog: owners use `/admin/catalog` for category/product/variant management; attendants use it as a read-only catalog view.
- Inventory: owners and attendants use `/admin/inventory` for fast stock updates.
- Commerce settings: owners use `/admin/settings`, `/admin/settings/delivery-zones`, and `/admin/settings/pickup` for delivery and pickup configuration.

## Django admin coexistence

Django admin remains available at `/admin/` on the backend service.

Use Django admin when:

- a custom dashboard screen is unavailable or blocked
- a superuser needs low-level model inspection
- emergency edits are needed during launch support
- bulk data cleanup is easier through Django admin
- debugging requires raw model relationships

Do not remove Django admin from production as part of the custom dashboard rollout.

## Permission checklist

- Signed-out users should be redirected away from `/admin`.
- Signed-in non-staff users should see a restricted-access state.
- Attendants should not see Staff or Settings navigation.
- Attendants should not see catalog create/edit controls.
- Attendants should be able to update stock through Inventory.
- Owners should see Staff, Settings, and all catalog management controls.

## Verification checklist

- `GET /api/v1/admin/me` returns the active staff role.
- `GET /api/v1/admin/permissions` matches the expected role permissions.
- `/admin` dashboard loads operational summary data.
- `/admin/staff` is owner-only.
- `/admin/settings` is owner-only.
- Inventory stock updates are reflected on the storefront product detail and checkout validation.
- Delivery-zone and pickup changes are reflected in checkout quote and pickup-info responses.
