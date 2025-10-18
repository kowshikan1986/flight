"""Payment tracking models."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.db import models

from core.models import TimeStampedModel


class Payment(TimeStampedModel):
	class PaymentProvider(models.TextChoices):
		STRIPE = 'stripe', 'Stripe'
		TEST = 'test', 'Test'

	class Status(models.TextChoices):
		INITIATED = 'initiated', 'Initiated'
		AUTHORIZED = 'authorized', 'Authorized'
		SUCCEEDED = 'succeeded', 'Succeeded'
		FAILED = 'failed', 'Failed'
		REFUNDED = 'refunded', 'Refunded'

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
	content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
	object_id = models.PositiveIntegerField()
	content_object = GenericForeignKey('content_type', 'object_id')
	amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.0'))])
	currency = models.CharField(max_length=3, default='usd')
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIATED)
	provider = models.CharField(max_length=20, choices=PaymentProvider.choices, default=PaymentProvider.STRIPE)
	provider_reference = models.CharField(max_length=100, blank=True)
	client_secret = models.CharField(max_length=120, blank=True)
	metadata = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['content_type', 'object_id']),
			models.Index(fields=['provider_reference']),
		]

	def __str__(self):  # pragma: no cover
		return f"Payment {self.provider_reference or self.pk}" 
