"""Context processors for template-wide configuration."""

from django.conf import settings
from .models import SiteSettings

def global_settings(request):
    return {
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "support_email": settings.DEFAULT_FROM_EMAIL,
        "hotels_enabled": getattr(settings, "FEATURE_HOTELS_ENABLED", True),
    }

def site_settings(request):
    settings_obj, created = SiteSettings.objects.get_or_create(pk=1)
    return {
        'site_settings': settings_obj,
    }
