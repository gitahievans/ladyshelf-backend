# Environment Reference

This backend is configured through environment variables loaded from `.env`.

## Core Django

| Variable | Required | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | yes in production | Django signing secret |
| `DJANGO_DEBUG` | yes | Enables debug mode locally |
| `DJANGO_ALLOWED_HOSTS` | yes | Comma-separated host allowlist |
| `DJANGO_CORS_ALLOWED_ORIGINS` | yes | Comma-separated frontend origins |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | recommended | Comma-separated CSRF trusted origins |
| `DJANGO_TIME_ZONE` | optional | Defaults to `Africa/Nairobi` |
| `DJANGO_LOG_LEVEL` | optional | Defaults to `INFO` |
| `DJANGO_LOG_STRUCTURED` | optional | Set to `true` for JSON logs |
| `DJANGO_ADMINS` | recommended in production | Comma-separated `Name:email@example.com` values for error emails |

## Database

| Variable | Required | Purpose |
| --- | --- | --- |
| `DJANGO_DB_ENGINE` | optional | Defaults to SQLite locally |
| `POSTGRES_DB` | required for Postgres | Database name |
| `POSTGRES_USER` | required for Postgres | Database user |
| `POSTGRES_PASSWORD` | required for Postgres | Database password |
| `POSTGRES_HOST` | required for Postgres | Database host |
| `POSTGRES_PORT` | required for Postgres | Database port |

## Supabase Auth

| Variable | Required | Purpose |
| --- | --- | --- |
| `SUPABASE_URL` | yes | Base project URL used for JWT issuer/JWKS |
| `SUPABASE_JWKS_URL` | optional | Override JWKS URL if needed |

## Email / Notifications

| Variable | Required | Purpose |
| --- | --- | --- |
| `DJANGO_DEFAULT_FROM_EMAIL` | yes | Default sender for transactional mail |
| `DJANGO_EMAIL_BACKEND` | optional | Console backend in debug, SMTP in production |
| `DJANGO_EMAIL_HOST` | required for SMTP | SMTP host |
| `DJANGO_EMAIL_PORT` | required for SMTP | SMTP port |
| `DJANGO_EMAIL_HOST_USER` | optional | SMTP username |
| `DJANGO_EMAIL_HOST_PASSWORD` | optional | SMTP password |
| `DJANGO_EMAIL_USE_TLS` | optional | TLS toggle |
| `DJANGO_EMAIL_USE_SSL` | optional | SSL toggle |
| `ORDER_NOTIFICATION_STAFF_EMAILS` | recommended | Comma-separated store/staff alert recipients |

## SasaPay

| Variable | Required | Purpose |
| --- | --- | --- |
| `SASAPAY_BASE_URL` | yes | Sandbox or production API base URL |
| `SASAPAY_CLIENT_ID` | yes for payment flows | App client ID |
| `SASAPAY_CLIENT_SECRET` | yes for payment flows | App client secret |
| `SASAPAY_MERCHANT_CODE` | yes for payment flows | Merchant code |
| `SASAPAY_CALLBACK_URL` | yes for payment flows | Public callback endpoint |
| `SASAPAY_TIMEOUT_SECONDS` | optional | HTTP timeout for SasaPay requests |

## Order expiry

| Variable | Required | Purpose |
| --- | --- | --- |
| `PREPAID_ORDER_EXPIRY_MINUTES` | optional | Defaults to `30` minutes |

## Production checklist

1. Set `DJANGO_DEBUG=false`.
2. Set `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`, and `DJANGO_CSRF_TRUSTED_ORIGINS` to the real frontend/backend hosts.
3. Configure `DJANGO_ADMINS` so unhandled production errors trigger email alerts.
4. Switch `SASAPAY_BASE_URL` and related credentials from sandbox to live only after merchant go-live approval.
