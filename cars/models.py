"""Car rental models."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from core.models import ReferenceNumberMixin, TimeStampedModel


class Car(TimeStampedModel):
	company = models.CharField(max_length=120)
	model = models.CharField(max_length=120)
	category = models.CharField(max_length=80)
	seats = models.PositiveIntegerField(default=4)
	luggage_capacity = models.PositiveIntegerField(default=2)
	location = models.CharField(max_length=255)
	price_per_day = models.DecimalField(max_digits=8, decimal_places=2)
	image = models.ImageField(upload_to='cars', blank=True, null=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ['company', 'model']

	def __str__(self):  # pragma: no cover
		return f"{self.company} {self.model}"


class CarAvailability(TimeStampedModel):
	car = models.ForeignKey(Car, related_name='availabilities', on_delete=models.CASCADE)
	date = models.DateField()
	is_available = models.BooleanField(default=True)

	class Meta:
		unique_together = ('car', 'date')
		ordering = ['date']

	def __str__(self):  # pragma: no cover
		return f"{self.car} on {self.date}: {'available' if self.is_available else 'unavailable'}"


class CarBooking(TimeStampedModel, ReferenceNumberMixin):
	class BookingStatus(models.TextChoices):
		BOOKED = 'booked', 'Booked'
		IN_PROGRESS = 'in_progress', 'In Progress'
		COMPLETED = 'completed', 'Completed'
		CANCELLED = 'cancelled', 'Cancelled'

	class PaymentStatus(models.TextChoices):
		PENDING = 'pending', 'Pending'
		AUTHORIZED = 'authorized', 'Authorized'
		SETTLED = 'settled', 'Settled'
		REFUNDED = 'refunded', 'Refunded'

	user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='carbookings', on_delete=models.CASCADE)
	car = models.ForeignKey(Car, related_name='bookings', on_delete=models.PROTECT)
	pickup_location = models.CharField(max_length=255)
	dropoff_location = models.CharField(max_length=255)
	pickup_date = models.DateField()
	dropoff_date = models.DateField()
	total_price = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal('0.0'))])
	status = models.CharField(max_length=20, choices=BookingStatus.choices, default=BookingStatus.BOOKED)
	payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
	payment_reference = models.CharField(max_length=64, blank=True)
	contact_email = models.EmailField()

	class Meta:
		ordering = ['-created_at']
		indexes = [models.Index(fields=['reference_number'])]

	def clean(self):
		if self.pickup_date >= self.dropoff_date:
			raise ValidationError('Drop-off date must be after pick-up date.')

	def rental_days(self) -> int:
		return (self.dropoff_date - self.pickup_date).days

	def __str__(self):  # pragma: no cover
		return f"Car booking {self.reference_number}"
