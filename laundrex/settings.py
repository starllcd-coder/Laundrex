from pathlib import Path
import os
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DJANGO_ENV = os.getenv("DJANGO_ENV", "development").strip().lower()
IS_PRODUCTION = DJANGO_ENV in {"production", "prod"}

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",

    "apps.core",
    "apps.accounts",
    "apps.management",
    "apps.pos",
    "apps.orders",
    "apps.payments",
    "apps.reports",
    "apps.settings_app",
    "apps.catalog",
    "apps.mobile_api",

]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ErrorLogMiddleware",
]

ROOT_URLCONF = "laundrex.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.accounts.context_processors.active_branch_label",
            ],
        },
    },
]

WSGI_APPLICATION = "laundrex.wsgi.application"

DB_NAME = os.getenv("DB_NAME") or os.getenv("PGDATABASE")
DB_USER = os.getenv("DB_USER") or os.getenv("PGUSER")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD")
DB_HOST = os.getenv("DB_HOST") or os.getenv("PGHOST")
DB_PORT = os.getenv("DB_PORT") or os.getenv("PGPORT", "5432")

if DB_NAME:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DB_NAME,
            "USER": DB_USER,
            "PASSWORD": DB_PASSWORD,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("ar", "Arabic")]
TIME_ZONE = "Asia/Muscat"
USE_I18N = True
USE_TZ = True

LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

# CORS for Flutter web (dev)
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "1" if DEBUG else "0") == "1"
CORS_ALLOWED_ORIGINS = [
    "http://localhost:54408",
    "http://127.0.0.1:54408",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

LOYALTY_POINTS_PER_OMR = int(os.getenv("LOYALTY_POINTS_PER_OMR", "1"))
DEFAULT_VIP_DISCOUNT_PERCENT = float(os.getenv("DEFAULT_VIP_DISCOUNT_PERCENT", "10"))
LOYALTY_REDEEM_VALUE_PER_POINT = float(os.getenv("LOYALTY_REDEEM_VALUE_PER_POINT", "0.01"))

SITE_BASE_URL = os.getenv("SITE_BASE_URL", "http://127.0.0.1:8000")

DEFAULT_READY_HOURS = int(os.getenv("DEFAULT_READY_HOURS", "24"))
READY_MINUTES_PER_ITEM = int(os.getenv("READY_MINUTES_PER_ITEM", "10"))

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "0") == "1"
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v18.0")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")

# Mobile app feature flags
SOCIAL_GOOGLE_ENABLED = os.getenv("SOCIAL_GOOGLE_ENABLED", "0") == "1"
SOCIAL_APPLE_ENABLED = os.getenv("SOCIAL_APPLE_ENABLED", "0") == "1"
SOCIAL_ALLOW_UNVERIFIED = os.getenv("SOCIAL_ALLOW_UNVERIFIED", "0") == "1"
CARD_PAY_ENABLED = os.getenv("CARD_PAY_ENABLED", "0") == "1"
APPLE_PAY_ENABLED = os.getenv("APPLE_PAY_ENABLED", "0") == "1"
GOOGLE_PAY_ENABLED = os.getenv("GOOGLE_PAY_ENABLED", "0") == "1"
ANALYTICS_ENABLED = os.getenv("ANALYTICS_ENABLED", "0") == "1"
BANK_TRANSFER_ENABLED = os.getenv("BANK_TRANSFER_ENABLED", "1") == "1"
OTP_DEBUG_RETURN_CODE = DEBUG and os.getenv("OTP_DEBUG_RETURN_CODE", "0") == "1"
BANK_TRANSFER_BANK_NAME = os.getenv("BANK_TRANSFER_BANK_NAME", "")
BANK_TRANSFER_ACCOUNT_NAME = os.getenv("BANK_TRANSFER_ACCOUNT_NAME", "")
BANK_TRANSFER_ACCOUNT_NUMBER = os.getenv("BANK_TRANSFER_ACCOUNT_NUMBER", "")
BANK_TRANSFER_IBAN = os.getenv("BANK_TRANSFER_IBAN", "")
BANK_TRANSFER_INSTRUCTIONS = os.getenv(
    "BANK_TRANSFER_INSTRUCTIONS",
    "Use your order number as reference and upload transfer proof if available.",
)

# Hybrid sync settings (desktop <-> cloud)
SYNC_ENABLED = os.getenv("SYNC_ENABLED", "0") == "1"
SYNC_ENDPOINTS_ENABLED = os.getenv("SYNC_ENDPOINTS_ENABLED", "0") == "1"
SYNC_API_TOKEN = os.getenv("SYNC_API_TOKEN", "")
CLOUD_BASE_URL = os.getenv("CLOUD_BASE_URL", "")
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "120"))

# Central Platform connector integration
CENTRAL_PLATFORM_URL = os.getenv("CENTRAL_PLATFORM_URL", "http://127.0.0.1:8000")
CENTRAL_CONNECTOR_SECRET = os.getenv("CENTRAL_CONNECTOR_SECRET", "")
CENTRAL_CONNECTOR_SIGNED = os.getenv("CENTRAL_CONNECTOR_SIGNED", "0") == "1"
CENTRAL_TENANT_CODE = os.getenv("CENTRAL_TENANT_CODE", "")
CENTRAL_MODULE_CODE = os.getenv("CENTRAL_MODULE_CODE", "laundrex")
CENTRAL_CONNECTOR_MAX_SKEW_SECONDS = int(os.getenv("CENTRAL_CONNECTOR_MAX_SKEW_SECONDS", "300"))

# Security (enable via env when deploying)
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "0") == "1"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "0") == "1"
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "0") == "1"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "0") == "1"

if IS_PRODUCTION:
    if SECRET_KEY in {"", "dev-only-change-me", "change-me"}:
        raise RuntimeError("DJANGO_SECRET_KEY must be set to a strong value in production.")
    if not any(h and h not in {"127.0.0.1", "localhost"} for h in ALLOWED_HOSTS):
        raise RuntimeError("DJANGO_ALLOWED_HOSTS must include production hostnames.")
    if CENTRAL_CONNECTOR_SECRET in {"", "dev-connector-secret"}:
        raise RuntimeError("CENTRAL_CONNECTOR_SECRET must be set to a strong value in production.")
    if not CENTRAL_CONNECTOR_SIGNED:
        raise RuntimeError("CENTRAL_CONNECTOR_SIGNED=1 is required in production.")
    if not CENTRAL_TENANT_CODE:
        raise RuntimeError("CENTRAL_TENANT_CODE is required in production.")
    if CENTRAL_CONNECTOR_SIGNED and not CENTRAL_CONNECTOR_SECRET:
        raise RuntimeError("CENTRAL_CONNECTOR_SIGNED=1 requires CENTRAL_CONNECTOR_SECRET.")

