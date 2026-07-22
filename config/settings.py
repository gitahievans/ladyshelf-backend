from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-wahi-local-dev-key")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CORS_ALLOWED_ORIGINS = env_list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "admin_portal",
    "common",
    "customers",
    "catalog",
    "checkout",
    "wishlist",
    "orders",
    "payments",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", not DEBUG)
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"


DATABASES = {
    "default": {
        "ENGINE": os.getenv("DJANGO_DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("POSTGRES_DB", str(BASE_DIR / "db.sqlite3")),
        "USER": os.getenv("POSTGRES_USER", ""),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", ""),
        "PORT": os.getenv("POSTGRES_PORT", ""),
        "CONN_MAX_AGE": int(os.getenv("DJANGO_DB_CONN_MAX_AGE", "0" if DEBUG else "60")),
        "CONN_HEALTH_CHECKS": True,
    }
}

if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"

TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Africa/Nairobi")

USE_I18N = True

USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


def parse_admins(value: str) -> list[tuple[str, str]]:
    admins: list[tuple[str, str]] = []
    for item in value.split(","):
        entry = item.strip()
        if not entry:
            continue

        if ":" in entry:
            name, email = entry.split(":", 1)
            admins.append((name.strip(), email.strip()))
        else:
            admins.append((entry, entry))

    return admins

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_JWKS_URL = os.getenv(
    "SUPABASE_JWKS_URL",
    f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else "",
)
SUPABASE_ISSUER = f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else ""

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "customers.auth.SupabaseJWTAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("DRF_THROTTLE_ANON", "120/minute"),
        "user": os.getenv("DRF_THROTTLE_USER", "240/minute"),
        "health": os.getenv("DRF_THROTTLE_HEALTH", "240/minute"),
        "catalog": os.getenv("DRF_THROTTLE_CATALOG", "120/minute"),
        "checkout_info": os.getenv("DRF_THROTTLE_CHECKOUT_INFO", "60/minute"),
        "checkout_quote": os.getenv("DRF_THROTTLE_CHECKOUT_QUOTE", "30/minute"),
        "checkout_order": os.getenv("DRF_THROTTLE_CHECKOUT_ORDER", "20/hour"),
        "payment_session": os.getenv("DRF_THROTTLE_PAYMENT_SESSION", "20/hour"),
        "payment_status_sync": os.getenv("DRF_THROTTLE_PAYMENT_STATUS_SYNC", "60/hour"),
        "payments_callback": os.getenv("DRF_THROTTLE_PAYMENTS_CALLBACK", "240/minute"),
        "account": os.getenv("DRF_THROTTLE_ACCOUNT", "120/minute"),
        "account_orders": os.getenv("DRF_THROTTLE_ACCOUNT_ORDERS", "120/minute"),
        "wishlist": os.getenv("DRF_THROTTLE_WISHLIST", "120/minute"),
        "admin": os.getenv("DRF_THROTTLE_ADMIN", "240/minute"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Wahi Fashion API",
    "DESCRIPTION": "Backend API for Wahi Fashion's ecommerce platform.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

structured_logging_enabled = os.getenv("DJANGO_LOG_STRUCTURED", "false").lower() == "true"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "structured": {
            "()": "common.logging.StructuredConsoleFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured" if structured_logging_enabled else "default",
        },
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
        },
    },
    "root": {
        "handlers": ["console", "mail_admins"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
}

ADMIN_SITE_HEADER = "Wahi Fashion Admin"
ADMIN_SITE_TITLE = "Wahi Fashion Admin Portal"
ADMIN_INDEX_TITLE = "Store Operations"
ADMINS = parse_admins(os.getenv("DJANGO_ADMINS", ""))

DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "orders@wahifashion.com")
EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("DJANGO_EMAIL_USE_TLS", "false").lower() == "true"
EMAIL_USE_SSL = os.getenv("DJANGO_EMAIL_USE_SSL", "false").lower() == "true"
ORDER_NOTIFICATION_STAFF_EMAILS = [
    email.strip()
    for email in os.getenv("ORDER_NOTIFICATION_STAFF_EMAILS", "").split(",")
    if email.strip()
]

SASAPAY_BASE_URL = os.getenv("SASAPAY_BASE_URL", "https://sandbox.sasapay.app")
SASAPAY_CLIENT_ID = os.getenv("SASAPAY_CLIENT_ID", "")
SASAPAY_CLIENT_SECRET = os.getenv("SASAPAY_CLIENT_SECRET", "")
SASAPAY_MERCHANT_CODE = os.getenv("SASAPAY_MERCHANT_CODE", "")
SASAPAY_CALLBACK_URL = os.getenv("SASAPAY_CALLBACK_URL", "")
SASAPAY_TIMEOUT_SECONDS = float(os.getenv("SASAPAY_TIMEOUT_SECONDS", "30"))
PREPAID_ORDER_EXPIRY_MINUTES = int(os.getenv("PREPAID_ORDER_EXPIRY_MINUTES", "30"))

IMAGE_GENERATION_ENABLED = env_bool("IMAGE_GENERATION_ENABLED", False)
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_WORKERS_AI_API_TOKEN = os.getenv("CLOUDFLARE_WORKERS_AI_API_TOKEN", "")
CLOUDFLARE_IMAGE_MODEL = os.getenv(
    "CLOUDFLARE_IMAGE_MODEL",
    "@cf/black-forest-labs/flux-2-klein-4b",
)
CLOUDFLARE_AI_TIMEOUT_SECONDS = float(os.getenv("CLOUDFLARE_AI_TIMEOUT_SECONDS", "90"))
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
PRODUCT_IMAGES_BUCKET = os.getenv("PRODUCT_IMAGES_BUCKET", "product-images")
