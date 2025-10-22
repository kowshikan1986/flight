"""Travel Booking settings module."""

from __future__ import annotations

import os
import sys
import warnings
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables early so they affect downstream config.
load_dotenv(BASE_DIR / ".env")

IS_TESTING = 'test' in sys.argv


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "True"

ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*,jaffna-main-eab4626.kuberns.cloud.").split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "http://jaffna-main-eab4626.kuberns.cloud.").split(",") if origin.strip()]

FEATURE_HOTELS_ENABLED = os.getenv("FEATURE_HOTELS_ENABLED", "true").lower() == "true"


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'rest_framework',
    'django_filters',
    'corsheaders',
    'core',
    'accounts',
    'hotels',
    'flights',
    'cars',
    'payments',
    'dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'travel_booking.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.global_settings',
                'core.context_processors.site_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'travel_booking.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL', f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:overview'
LOGOUT_REDIRECT_URL = 'accounts:login'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 25))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'false').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@travel-booking.local')

def _clean_env_value(*names: str) -> str:
    """Return the first non-placeholder env var value from the provided names."""

    placeholders = {
        'sk_test_your_stripe_secret_key',
        'pk_test_your_stripe_publishable_key',
        'sk_live_your_stripe_secret_key',
        'pk_live_your_stripe_publishable_key',
        'your-stripe-secret-key',
        'your-stripe-publishable-key',
        'whsec_your_webhook_secret',
    }

    for name in names:
        raw_value = os.getenv(name, '')
        if not raw_value:
            continue
        value = raw_value.strip()
        if not value:
            continue
        if value.lower() in placeholders:
            continue
        return value
    return ''


STRIPE_MODE = os.getenv('STRIPE_MODE', 'test' if DEBUG else 'live').strip().lower()
if STRIPE_MODE not in {'test', 'live'}:
    warnings.warn(
        f"Unknown STRIPE_MODE '{STRIPE_MODE}' specified. Falling back to 'test'.",
        stacklevel=2,
    )
    STRIPE_MODE = 'test'

secret_key_env_order = ['STRIPE_SECRET_KEY']
publishable_key_env_order = ['STRIPE_PUBLISHABLE_KEY']

if STRIPE_MODE == 'live':
    secret_key_env_order.insert(0, 'STRIPE_LIVE_SECRET_KEY')
    publishable_key_env_order.insert(0, 'STRIPE_LIVE_PUBLISHABLE_KEY')
else:
    secret_key_env_order.insert(0, 'STRIPE_TEST_SECRET_KEY')
    publishable_key_env_order.insert(0, 'STRIPE_TEST_PUBLISHABLE_KEY')


STRIPE_SECRET_KEY = _clean_env_value(*secret_key_env_order)
STRIPE_PUBLISHABLE_KEY = _clean_env_value(*publishable_key_env_order)
STRIPE_WEBHOOK_SECRET = _clean_env_value('STRIPE_WEBHOOK_SECRET')

if not STRIPE_SECRET_KEY or not STRIPE_PUBLISHABLE_KEY:
    if IS_TESTING or DEBUG:
        if not STRIPE_SECRET_KEY:
            STRIPE_SECRET_KEY = f"sk_{STRIPE_MODE}_placeholder"
        if not STRIPE_PUBLISHABLE_KEY:
            STRIPE_PUBLISHABLE_KEY = f"pk_{STRIPE_MODE}_placeholder"
        warnings.warn(
            "Stripe keys are not configured; falling back to placeholders. "
            "Provide real keys in your environment when running against Stripe.",
            stacklevel=2,
        )
    else:
        raise ImproperlyConfigured(
            "Stripe keys are missing. Set STRIPE_MODE and the corresponding "
            "STRIPE_<MODE>_SECRET_KEY/STRIPE_<MODE>_PUBLISHABLE_KEY (or the "
            "generic STRIPE_SECRET_KEY/STRIPE_PUBLISHABLE_KEY) in your environment."
        )

expected_secret_prefix = f"sk_{STRIPE_MODE}_"
expected_publishable_prefix = f"pk_{STRIPE_MODE}_"

if not STRIPE_SECRET_KEY.startswith(expected_secret_prefix):
    warnings.warn(
        "Stripe secret key prefix does not match STRIPE_MODE. Double-check the configured keys.",
        stacklevel=2,
    )

if not STRIPE_PUBLISHABLE_KEY.startswith(expected_publishable_prefix):
    warnings.warn(
        "Stripe publishable key prefix does not match STRIPE_MODE. Double-check the configured keys.",
        stacklevel=2,
    )

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if origin.strip()]
CORS_ALLOW_ALL_ORIGINS = not CORS_ALLOWED_ORIGINS

SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'false').lower() == 'true'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_BEAT_SCHEDULE = {}
