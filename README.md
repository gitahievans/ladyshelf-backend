# Ladyshelf Backend

This directory contains the Django backend for Ladyshelf.

## Current scope

The backend now covers the MVP commerce flow through Phase 8:

- Supabase-authenticated customer accounts plus guest checkout
- catalog, wishlist, checkout rules, order creation, and account history
- SasaPay sandbox payments and unpaid prepay expiry handling
- Django admin for operations with bootstrapped `Owner` and `Attendant` roles
- API throttling, structured logging support, and operational runbooks for launch prep

## Local setup

1. Copy `.env.example` to `.env`
2. Create or reuse the project virtualenv
3. Install dependencies from `requirements.txt`
4. Run migrations
5. Run `python manage.py bootstrap_admin_roles`
6. Start the server with `python manage.py runserver`

## Operational docs

- Environment variables: `docs/environment.md`
- Launch and backoffice runbook: `docs/launch-runbook.md`
- Production container deployment: `deploy/README.md`

## Useful management commands

- `python manage.py bootstrap_admin_roles`
- `python manage.py expire_unpaid_prepay_orders`

## Launch readiness notes

- Catalog and checkout defaults are seeded by migrations.
- Public and account-adjacent APIs are rate-limited via DRF throttling.
- Set `DJANGO_LOG_STRUCTURED=true` for JSON logs in production.
- Set `DJANGO_ADMINS` to receive Django error emails for unhandled production failures.

## Useful URLs

- Admin: `/admin/`
- Health check: `/api/v1/health`
- Schema: `/api/schema/`
- Swagger UI: `/api/docs/swagger/`
- ReDoc: `/api/docs/redoc/`
