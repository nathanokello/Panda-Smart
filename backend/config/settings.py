"""Settings for the Panda Smart Django backend.

Configuration comes from environment variables so the same code runs with SQLite
locally and PostgreSQL in deployment (see architecture.md, Sections 2 and 4).
"""
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# .env.example documents every setting; load a local .env when present.
load_dotenv(BASE_DIR / ".env")


def database_from_url(url: str) -> dict:
    """Translate DATABASE_URL into a Django DATABASES['default'] dict."""
    parsed = urlparse(url)
    if parsed.scheme.startswith("sqlite"):
        path = unquote(parsed.path)
        # sqlite:///C:/... yields '/C:/...' on Windows.
        if os.name == "nt" and re.match(r"^/[A-Za-z]:", path):
            path = path[1:]
        if not path:
            path = str(BASE_DIR / "db.sqlite3")
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": path}
    if parsed.scheme in ("postgres", "postgresql"):
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
        }
    raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme!r}")


default_db_url = "sqlite:///" + str(BASE_DIR / "db.sqlite3").replace("\\", "/")
DATABASES = {"default": database_from_url(os.environ.get("DATABASE_URL", default_db_url))}

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "corsheaders",
    "core",
    "records",
    "planting",
    "geoagri",
    "seed",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
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
ASGI_APPLICATION = "config.asgi.application"

AUTH_USER_MODEL = "core.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("core.authentication.ExpiringTokenAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "login_phone": os.environ.get("LOGIN_PHONE_RATE", "20/hour"),
        "register": "5/min",
        "verify": "30/min",
        "ussd": "60/min",
        "geoagri_read": "120/hour",
        "geoagri_write": "30/hour",
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Panda Smart API",
    "DESCRIPTION": "Backend for the Panda Smart crop-lifecycle demo (architecture.md).",
    "VERSION": "1.0.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SERVE_AUTHENTICATION": [],
    "AUTHENTICATION_WHITELIST": ["core.authentication.ExpiringTokenAuthentication"],
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        # 5500: the HTML frontend served with `python -m http.server 5500` or Live Server.
        "http://localhost:5500,http://127.0.0.1:5500,http://localhost:5173,http://localhost:3000",
    ).split(",")
    if origin.strip()
]
CORS_ALLOW_ALL_ORIGINS = DEBUG and not CORS_ALLOWED_ORIGINS

# Project-specific settings
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://127.0.0.1:5500").rstrip("/")
# Path of the public verify page. The HTML frontend is static files, so the
# token goes in the query string: verify.html?token=<token>.
FRONTEND_VERIFY_PATH = os.environ.get("FRONTEND_VERIFY_PATH", "/verify.html?token=")
# Tenant name for farmers who register themselves (default: oldest cooperative).
SELF_REGISTER_TENANT = os.environ.get("SELF_REGISTER_TENANT", "")
VERIFY_TOKEN_TTL_DAYS = int(os.environ.get("VERIFY_TOKEN_TTL_DAYS", "14"))
HIFADHI_MAIZE_MAX_MOISTURE_PCT = float(
    os.environ.get("HIFADHI_MAIZE_MAX_MOISTURE_PCT", "13.0")
)
if not 0 <= HIFADHI_MAIZE_MAX_MOISTURE_PCT <= 100:
    raise ValueError("HIFADHI_MAIZE_MAX_MOISTURE_PCT must be between 0 and 100.")
HIFADHI_CHECK_DAYS = tuple(
    int(day.strip())
    for day in os.environ.get("HIFADHI_CHECK_DAYS", "14,30,60").split(",")
    if day.strip()
)
if not HIFADHI_CHECK_DAYS or any(day <= 0 for day in HIFADHI_CHECK_DAYS):
    raise ValueError("HIFADHI_CHECK_DAYS must contain positive day counts.")
# Sign-in tokens expire after this many hours (0 = never). Default 7 days.
TOKEN_TTL_HOURS = int(os.environ.get("TOKEN_TTL_HOURS", "168"))
# Rainfall used by planting advice, first available wins (see planting/services.py).
RAINFALL_SOURCE_PRIORITY = [
    item.strip()
    for item in os.environ.get("RAINFALL_SOURCE_PRIORITY", "NASA_POWER,CHIRPS").split(",")
    if item.strip()
]
# Open-Meteo forecasts are free for NON-COMMERCIAL use only. Off by default.
OPEN_METEO_ENABLED = os.environ.get("OPEN_METEO_ENABLED", "0") == "1"
# Shared secret in the USSD callback URL (?key=...). Required when DEBUG is off.
USSD_CALLBACK_SECRET = os.environ.get("USSD_CALLBACK_SECRET", "")
AT_USERNAME = os.environ.get("AT_USERNAME", "sandbox")
AT_API_KEY = os.environ.get("AT_API_KEY", "")
