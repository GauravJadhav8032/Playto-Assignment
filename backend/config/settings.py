"""
Django settings for Payout Engine.

Reads sensitive values from environment variables with safe defaults
for local development. In production set all ENV vars properly.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------------------------------------------
# Security
# -------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-insecure-key-replace-in-prod",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")
# Automatically allow Render's subdomain
if not DEBUG:
    ALLOWED_HOSTS += [".onrender.com"]

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


# -------------------------------------------------------------------
# Applications
# -------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    "django_q",
    # Local
    "app",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serve static files on Render
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
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# -------------------------------------------------------------------
# Database — PostgreSQL (default) or SQLite (set USE_SQLITE=1 for local dev)
# -------------------------------------------------------------------
_use_sqlite = os.environ.get("USE_SQLITE", "0") == "1"

if _use_sqlite:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "payout_engine"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }

# -------------------------------------------------------------------
# Django REST Framework
# -------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

# -------------------------------------------------------------------
# Django-Q2 — ORM broker (no Redis)
# -------------------------------------------------------------------
Q_CLUSTER = {
    "name": "payout_engine",
    "workers": 2,
    "timeout": 60,       # task hard timeout seconds
    "retry": 120,        # re-queue if task not confirmed within N seconds
    "orm": "default",    # use Django ORM as message broker
    "catch_up": False,   # don't execute missed scheduled tasks on startup
}

# -------------------------------------------------------------------
# CORS — allow React dev server
# -------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = DEBUG  # wide-open in dev only
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# Add Vercel frontend URL in production via env var
# e.g. CORS_ALLOWED_ORIGIN=https://your-app.vercel.app
_vercel_origin = os.environ.get("CORS_ALLOWED_ORIGIN")
if _vercel_origin:
    CORS_ALLOWED_ORIGINS.append(_vercel_origin)

# -------------------------------------------------------------------
# Static files
# -------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# CompressedStaticFilesStorage (no manifest) — safe for both web and worker services.
# ManifestStaticFilesStorage requires collectstatic output which the worker build skips.
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------------------------
# Logging — minimal, structured
# -------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "app": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
