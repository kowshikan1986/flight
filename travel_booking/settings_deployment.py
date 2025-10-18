"""Production settings for Azure deployment."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F401,F403
from .settings import BASE_DIR as _BASE_DIR

BASE_DIR: Path = _BASE_DIR

secret_key = os.environ.get("DJANGO_SECRET_KEY") or os.environ.get("SECRET")
if secret_key:
    SECRET_KEY = secret_key
else:
    warnings.warn(
        "SECRET or DJANGO_SECRET_KEY environment variable not set; falling back to base SECRET_KEY.",
        stacklevel=2,
    )

hostname = os.environ.get("WEBSITE_HOSTNAME", "").strip()
if hostname:
    ALLOWED_HOSTS = [hostname]
    CSRF_TRUSTED_ORIGINS = [f"https://{hostname}"]
else:
    warnings.warn(
        "WEBSITE_HOSTNAME environment variable not set; using base ALLOWED_HOSTS.",
        stacklevel=2,
    )

DEBUG = False

if EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
    raise ImproperlyConfigured(
        "Console email backend is not allowed in production. Set EMAIL_BACKEND to an SMTP or service-specific backend "
        "and provide the necessary credentials via environment variables."
    )

if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    missing_email_settings: list[str] = []
    if not EMAIL_HOST:
        missing_email_settings.append("EMAIL_HOST")
    if not EMAIL_PORT:
        missing_email_settings.append("EMAIL_PORT")
    if not EMAIL_HOST_USER:
        missing_email_settings.append("EMAIL_HOST_USER")
    if not EMAIL_HOST_PASSWORD:
        missing_email_settings.append("EMAIL_HOST_PASSWORD")
    if missing_email_settings:
        raise ImproperlyConfigured(
            "SMTP email backend is configured but these settings are missing: "
            + ", ".join(missing_email_settings)
            + ". Set them as environment variables in your deployment."
        )

if DEFAULT_FROM_EMAIL.endswith("travel-booking.local"):
    warnings.warn(
        "DEFAULT_FROM_EMAIL is still using the local placeholder address. Update DEFAULT_FROM_EMAIL in the environment to a "
        "verified sender for production email delivery.",
        stacklevel=2,
    )

_original_middleware = MIDDLEWARE  # type: ignore[name-defined]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
]
for middleware in _original_middleware:
    if middleware == "django.middleware.security.SecurityMiddleware":
        continue
    if middleware == "whitenoise.middleware.WhiteNoiseMiddleware":
        continue
    MIDDLEWARE.append(middleware)

STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

conn_str = os.environ.get("AZURE_POSTGRESQL_CONNECTIONSTRING", "").strip()
if conn_str:
    conn_str_params: dict[str, str] = {}
    for pair in conn_str.split():
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        conn_str_params[key.strip()] = value.strip()

    required_keys = {"dbname", "host", "user", "password"}
    missing_keys = sorted(required_keys - conn_str_params.keys())
    if missing_keys:
        raise ImproperlyConfigured(
            "AZURE_POSTGRESQL_CONNECTIONSTRING is missing required keys: "
            + ", ".join(missing_keys)
        )

    DATABASES["default"] = {  # type: ignore[name-defined]
        "ENGINE": "django.db.backends.postgresql",
        "NAME": conn_str_params["dbname"],
        "HOST": conn_str_params["host"],
        "USER": conn_str_params["user"],
        "PASSWORD": conn_str_params["password"],
    }

    if "port" in conn_str_params:
        DATABASES["default"]["PORT"] = conn_str_params["port"]  # type: ignore[index]

    sslmode = conn_str_params.get("sslmode")
    if sslmode:
        DATABASES["default"].setdefault("OPTIONS", {})  # type: ignore[index]
        DATABASES["default"]["OPTIONS"]["sslmode"] = sslmode  # type: ignore[index]
else:
    warnings.warn(
        "AZURE_POSTGRESQL_CONNECTIONSTRING not set; using default database configuration.",
        stacklevel=2,
    )
