from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured
# noinspection PyPackageRequirements
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = Path(os.getenv("DJANGO_ENV_FILE", BASE_DIR / ".env"))
load_dotenv(ENV_FILE)


LOCAL_ALLOWED_HOSTS_DEFAULT = "127.0.0.1,localhost,::1,culineire.localhost"
LOCAL_CSRF_TRUSTED_ORIGINS_DEFAULT = (
    "http://127.0.0.1:8000,"
    "http://localhost:8000,"
    "http://culineire.localhost:8000"
)


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() == "true"


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def env_list(name: str, default: str = "") -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def database_from_url(url: str) -> dict:
    parsed = urlparse(url)

    if parsed.scheme in {"postgres", "postgresql"}:
        options = {}
        query = parse_qs(parsed.query)
        if "sslmode" in query and query["sslmode"]:
            options["sslmode"] = query["sslmode"][0]

        database = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
            "CONN_MAX_AGE": env_int("DJANGO_DB_CONN_MAX_AGE", 60 if IS_PRODUCTION else 0),
        }
        if options:
            database["OPTIONS"] = options
        return database

    if parsed.scheme == "sqlite":
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": unquote(parsed.path),
        }

    raise ImproperlyConfigured("DATABASE_URL must start with postgres://, postgresql://, or sqlite:///")


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY environment variable is not set. "
        "Add it to your environment or .env file before starting Django."
    )

DJANGO_ENV = os.getenv("DJANGO_ENV", "production").strip().lower()
IS_PRODUCTION = DJANGO_ENV == "production"
IS_TESTING = "test" in sys.argv

DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
SERVE_STATIC_LOCALLY = env_bool(
    "DJANGO_SERVE_STATIC_LOCALLY",
    default=not IS_PRODUCTION,
)
SERVE_MEDIA_LOCALLY = env_bool(
    "DJANGO_SERVE_MEDIA_LOCALLY",
    default=not IS_PRODUCTION,
)

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "" if IS_PRODUCTION else LOCAL_ALLOWED_HOSTS_DEFAULT,
)
if IS_PRODUCTION and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must be set when DJANGO_ENV=production."
    )

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "" if IS_PRODUCTION else LOCAL_CSRF_TRUSTED_ORIGINS_DEFAULT,
)

# Defensive guarantee for local development: even if DJANGO_ALLOWED_HOSTS
# (or DJANGO_CSRF_TRUSTED_ORIGINS) was overridden to a minimal list, make
# sure standard local hosts are always present. This avoids "DisallowedHost"
# every time someone forgets to update their .env after pulling new code.
if not IS_PRODUCTION:
    for host in LOCAL_ALLOWED_HOSTS_DEFAULT.split(","):
        host = host.strip()
        if host and host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)
    for origin in LOCAL_CSRF_TRUSTED_ORIGINS_DEFAULT.split(","):
        origin = origin.strip()
        if origin and origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "recipes",
    "articles",
    "messaging",
    "presence",
    "monitoring",
    "collection",
    "legal",
    "newsfeed",
    "sandbox",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "monitoring.middleware.MonitoringMiddleware",
    "config.csp_middleware.CspNonceMiddleware",
    "config.maintenance.MaintenanceModeMiddleware",
]

# ── Monitoring ─────────────────────────────────────────────────────────────
MAINTENANCE_MODE = env_bool("DJANGO_MAINTENANCE_MODE", default=False)
MAINTENANCE_UNTIL = os.getenv("DJANGO_MAINTENANCE_UNTIL", "")
MAINTENANCE_RETRY_AFTER_SECONDS = env_int("DJANGO_MAINTENANCE_RETRY_AFTER_SECONDS", 10800)

MONITORING_ENABLED = env_bool("MONITORING_ENABLED", default=True)
MONITORING_RETENTION_DAYS = env_int("MONITORING_RETENTION_DAYS", default=90)
MONITORING_ANONYMIZE_IP = env_bool("MONITORING_ANONYMIZE_IP", default=True)
MONITORING_EXCLUDED_PATH_PREFIXES = [
    "/static/",
    "/media/",
    "/admin/jsi18n/",
    "/favicon.ico",
    "/robots.txt",
    "/presence/",
]

ROOT_URLCONF = "config.urls"

template_context_processors = [
    "django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth",
    "django.contrib.messages.context_processors.messages",
    "recipes.context_processors.header_author",
]
if DEBUG:
    template_context_processors.insert(1, "django.template.context_processors.debug")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": template_context_processors,
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    DATABASES = {
        "default": database_from_url(DATABASE_URL),
    }
else:
    DATABASES = {
        "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        }
    }

if IS_TESTING:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "culineire-tests",
        }
    }
else:
    CACHE_DIR = Path(os.getenv("DJANGO_CACHE_DIR", str(BASE_DIR / "cache")))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": str(CACHE_DIR),
            "TIMEOUT": 3600,
        }
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
TIME_ZONE = "Europe/Dublin"
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(os.getenv("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
            if IS_PRODUCTION
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_BYTES
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755


LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# ── Email ──────────────────────────────────────────────────────────────────
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if not IS_PRODUCTION
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 10)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "CulinEire <noreply@culineire.ie>")
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "127.0.0.1:8000")
SITE_SCHEME = os.getenv("SITE_SCHEME", "https" if IS_PRODUCTION else "http")
OWNER_SLUG = "greenbear"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
OPENAI_IMAGE_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "low")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
PRESENCE_EVENT_COOLDOWN_MINUTES = env_int("PRESENCE_EVENT_COOLDOWN_MINUTES", default=5)
SIGNUP_REQUIRE_EMAIL_CONFIRMATION = env_bool(
    "SIGNUP_REQUIRE_EMAIL_CONFIRMATION",
    default=IS_PRODUCTION,
)
PASSWORD_RESET_TIMEOUT = 86400  # activation link expires in 24 hours

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Cloudflare Turnstile ───────────────────────────────────────────────────
TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")

REPORT_NOTIFY_EMAIL = os.getenv("REPORT_NOTIFY_EMAIL", EMAIL_HOST_USER)


SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=IS_PRODUCTION)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", default=IS_PRODUCTION)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", default=IS_PRODUCTION)
SECURE_HSTS_SECONDS = env_int(
    "DJANGO_SECURE_HSTS_SECONDS",
    31536000 if IS_PRODUCTION else 0,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=True,
)
SECURE_HSTS_PRELOAD = env_bool(
    "DJANGO_SECURE_HSTS_PRELOAD",
    default=True,
)

if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


LOG_DIR = Path(os.getenv("DJANGO_LOG_DIR", str(BASE_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "DEBUG" if DEBUG else "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_sensitive_data": {
            "()": "config.logging_filters.RedactSensitiveDataFilter",
        },
    },
    "formatters": {
        "verbose": {
            "format": "{levelname} | {asctime} | {module:15} | {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "{levelname} | {message}",
            "style": "{",
        },
        "auth_failure": {
            "format": "{asctime} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["redact_sensitive_data"],
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "django.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["redact_sensitive_data"],
        },
        "auth_failures_file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "auth_failures.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "auth_failure",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "recipes": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "articles": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "auth.failures": {
            "handlers": ["auth_failures_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.security.DisallowedHost": {
            "handlers": [],
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

if IS_TESTING:
    LOGGING["handlers"]["null"] = {
        "class": "logging.NullHandler",
    }
    for logger_name in ("django", "django.request", "recipes", "articles"):
        LOGGING["loggers"][logger_name]["handlers"] = ["null"]
    LOGGING["loggers"]["auth.failures"]["handlers"] = ["null"]
