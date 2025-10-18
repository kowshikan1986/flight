"""Shared base models and mixins for the travel booking platform."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
	"""Abstract base model with created/updated timestamps."""

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		abstract = True


class ReferenceNumberMixin(models.Model):
	"""Adds a unique human-readable reference number."""

	reference_number = models.CharField(max_length=18, unique=True, editable=False)

	class Meta:
		abstract = True

	def save(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - deterministic save
		if not self.reference_number:
			self.reference_number = self.generate_reference()
		super().save(*args, **kwargs)

	@staticmethod
	def generate_reference(prefix: str | None = None) -> str:
		uid = uuid.uuid4().hex[:10].upper()
		return f"{prefix or 'BK'}-{uid[:4]}-{uid[4:]}"


class AvailabilityError(ValidationError):
	"""Raised when requested availability cannot be satisfied."""


def daterange(start_date, end_date):
	"""Yield dates from start_date to end_date (exclusive)."""

	current = start_date
	while current < end_date:
		yield current
		current += timedelta(days=1)


def send_booking_email(subject: str, message: str, recipient_list: list[str]) -> None:
	"""Send transactional booking emails safely."""

	if not recipient_list:
		return

	from django.core.mail import send_mail

	send_mail(
		subject,
		message,
		settings.DEFAULT_FROM_EMAIL,
		recipient_list,
		fail_silently=False,
	)


class SiteSettings(models.Model):
	logo = models.ImageField(upload_to='logos/', blank=True, null=True)
	custom_header = models.CharField(max_length=255, blank=True, default='')
	advertisement = models.TextField(blank=True, default='')
	hero_image = models.ImageField(upload_to='hero_banners/', blank=True, null=True)

	class Meta:
		verbose_name = 'Site Setting'
		verbose_name_plural = 'Site Settings'

	@property
	def hero_image_url(self) -> str:
		if self.hero_image:
			return self.hero_image.url
		return "https://images.unsplash.com/photo-1489515217757-5fd1be406fef?w=1920&h=600&auto=format&fit=crop"
