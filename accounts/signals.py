"""Signal handlers for automatic profile creation."""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CustomerProfile, User


@receiver(post_save, sender=User)
def create_user_profile(sender, instance: User, created: bool, **_: object) -> None:
    if created:
        CustomerProfile.objects.get_or_create(user=instance)
