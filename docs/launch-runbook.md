# Launch Runbook

## Core setup

1. Copy `.env.example` to `.env` and fill the production-safe values.
2. Run `python manage.py migrate`.
3. Run `python manage.py bootstrap_admin_roles`.
4. Create at least one superuser with `python manage.py createsuperuser`.
5. Confirm `/api/v1/health`, `/api/docs/swagger/`, and `/admin/` are reachable.

## Catalog and checkout defaults

- Catalog data is seeded from `catalog/fixtures/catalog_seed.json` during migrations.
- Delivery zones and the Roysambu pickup location are seeded by checkout migrations.
- For a fresh environment, migrations are the supported source of truth for initial seed data.

## Admin roles

- `Owner`
  - full catalog, checkout-config, customer, wishlist, order, and payment access
- `Attendant`
  - can view customer, wishlist, payment, and checkout-configuration data
  - can update `ProductVariant.stock`
  - can update `Order.order_status`, `Order.payment_status`, and `Order.internal_notes`
  - cannot add or delete orders or payment transactions

## Daily backoffice workflows

### Products and stock

1. Owners manage categories, products, and imagery in Django admin.
2. Attendants update stock from `Product variants`.
3. Out-of-stock variants remain visible on the storefront and automatically become non-purchasable.

### Orders

1. Review new orders in `Orders`.
2. For prepaid orders, confirm the payment state before dispatch.
3. Update `order_status` as fulfillment progresses.
4. Use `internal_notes` for manual delivery coordination or parcel follow-up.

### Payment verification

1. Review raw payment metadata in `Payment transactions`.
2. Use the checkout/order detail views to confirm the order state reflects the payment outcome.
3. If prepaid orders remain pending too long, run the expiry command or scheduled job.

## Scheduled task

- Expire unpaid prepaid orders:
  - `python manage.py expire_unpaid_prepay_orders`

Run this on a schedule before launch. The command cancels expired unpaid prepay orders and restores stock.

## Webhook setup

- SasaPay callback endpoint:
  - `/api/v1/payments/sasapay/callback`
- Ensure the callback URL is publicly reachable over HTTPS.
- After changing environments, update `SASAPAY_CALLBACK_URL` to the matching public backend URL.

## Observability

- Enable JSON logs with `DJANGO_LOG_STRUCTURED=true` when shipping logs to a platform collector.
- Configure `DJANGO_ADMINS` in production so Django can email unhandled error alerts to the operations team.

## Deferred backlog

- Customer/staff SMS via Africa's Talking
- SasaPay live-money rollout verification and reconciliation
- Optional Sentry integration if the launch environment needs deeper error aggregation
- Custom staff dashboard after the MVP stabilizes in Django admin
