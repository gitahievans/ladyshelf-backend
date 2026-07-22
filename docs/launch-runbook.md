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

## Backoffice surfaces

- Custom staff dashboard:
  - frontend route `/admin`
  - preferred interface for day-to-day operations
- Django admin:
  - backend route `/admin/`
  - remains available for fallback, emergency maintenance, superuser access, and deep model inspection

The custom dashboard and Django admin intentionally coexist. Do not treat the custom dashboard rollout as a reason to remove Django admin.

## Daily backoffice workflows

### Products and stock

1. Owners manage categories, products, variants, and imagery from the custom dashboard.
2. Attendants update stock from the custom dashboard Inventory page.
3. Out-of-stock variants remain visible on the storefront and automatically become non-purchasable.
4. Use Django admin as fallback for emergency or bulk maintenance.

### Orders

1. Review new orders in the custom dashboard Orders page.
2. For prepaid orders, confirm the payment state before dispatch.
3. Update `order_status` as fulfillment progresses.
4. Use `internal_notes` for manual delivery coordination or parcel follow-up.
5. Use Django admin as fallback if the custom dashboard is unavailable.

### Payment verification

1. Review raw payment metadata in the custom dashboard Payments page.
2. Use the checkout/order detail views to confirm the order state reflects the payment outcome.
3. If prepaid orders remain pending too long, run the expiry command or scheduled job.

### Staff access

1. Owners grant staff access in the custom dashboard Staff page.
2. Staff records link existing Supabase-backed customer profiles to an `owner` or `attendant` dashboard role.
3. Deactivate staff access instead of deleting records when preserving access history is useful.

## Scheduled task

- Expire unpaid prepaid orders:
  - `python manage.py expire_unpaid_prepay_orders`

Run this on a schedule before launch. The command cancels expired unpaid prepay orders and restores stock.

### AI product-image queue

- Inspect queued/reviewable work through `/api/v1/admin/image-generations/batches`.
- Process one product set manually with `python manage.py process_product_image_generations --limit 1`.
- The optional `ladyshelf-product-images.timer` runs that command every two minutes; do not enable it
  until credentials, quota expectations, and production activation are separately approved.
- Quota failures remain queued until the next 00:00 UTC reset. Transient failures use bounded retries.
- Configuration failures stop retrying and expose only a safe owner-facing message.
- Rejected candidates are never publishable. Owner regeneration uses structured controls and guarded
  notes rather than raw prompts. Regenerating Hero queues Hero, Alternate, and Detail because the latter
  two depend on its reference; regenerating Alternate or Detail affects only that slot.
- New sets use different frozen catalog colors whenever three or more exist, distinct adult Black-woman
  profiles for Hero and Alternate, and a person-free Detail prompt. Never select or request a color that
  is absent from the generation's frozen catalog snapshot.
- Explicit regeneration increments the candidate revision and seed. Worker retries must preserve the
  stored prompt and seed so transient failures remain reproducible.
- Publish copies all three approved objects to final paths before atomically replacing the gallery.
  Use `Restore previous gallery` in the admin review UI for rollback.

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
