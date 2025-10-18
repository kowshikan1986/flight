"""Hotel domain models."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.models import ReferenceNumberMixin, TimeStampedModel


class Hotel(TimeStampedModel):
	name = models.CharField(max_length=255)
	slug = models.SlugField(unique=True, blank=True)
	description = models.TextField()
	location = models.CharField(max_length=255)
	address = models.CharField(max_length=255)
	contact_email = models.EmailField()
	contact_phone = models.CharField(max_length=30)
	amenities = models.TextField(blank=True)
	thumbnail = models.ImageField(upload_to='hotels', blank=True, null=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ['name']

	def save(self, *args, **kwargs):  # pragma: no cover - slug generation is deterministic
		if not self.slug:
			self.slug = slugify(self.name)
		super().save(*args, **kwargs)

	def __str__(self):  # pragma: no cover - human readable
		return self.name


class RoomType(models.TextChoices):
	SINGLE = 'single', 'Single'
	DOUBLE = 'double', 'Double'
	FAMILY = 'family', 'Family'


class HotelRoomType(TimeStampedModel):
	hotel = models.ForeignKey(Hotel, related_name='room_types', on_delete=models.CASCADE)
	room_type = models.CharField(max_length=20, choices=RoomType.choices)
	base_price = models.DecimalField(max_digits=8, decimal_places=2)
	total_rooms = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
	description = models.TextField(blank=True)

	class Meta:
		unique_together = ('hotel', 'room_type')
		ordering = ['hotel__name']

	def __str__(self):  # pragma: no cover - human readable
		return f"{self.hotel.name} - {self.get_room_type_display()}"


class HotelRoomInventory(TimeStampedModel):
	room_type = models.ForeignKey(HotelRoomType, related_name='inventories', on_delete=models.CASCADE)
	date = models.DateField()
	available_rooms = models.PositiveIntegerField(default=0)

	class Meta:
		unique_together = ('room_type', 'date')
		ordering = ['date']

	def __str__(self):  # pragma: no cover
		return f"{self.room_type} availability on {self.date}: {self.available_rooms}"


class HotelBooking(TimeStampedModel, ReferenceNumberMixin):
	class BookingStatus(models.TextChoices):
		BOOKED = 'booked', 'Booked'
		CHECKED_IN = 'checked_in', 'Checked In'
		COMPLETED = 'completed', 'Completed'
		CANCELLED = 'cancelled', 'Cancelled'

	class PaymentStatus(models.TextChoices):
		PENDING = 'pending', 'Pending'
		AUTHORIZED = 'authorized', 'Authorized'
		SETTLED = 'settled', 'Settled'
		REFUNDED = 'refunded', 'Refunded'

	user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='hotelbookings', on_delete=models.CASCADE)
	room_type = models.ForeignKey(HotelRoomType, related_name='bookings', on_delete=models.PROTECT)
	check_in = models.DateField()
	check_out = models.DateField()
	guests = models.PositiveIntegerField(default=1)
	surname = models.CharField(max_length=120)
	contact_email = models.EmailField()
	total_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.0'))])
	status = models.CharField(max_length=20, choices=BookingStatus.choices, default=BookingStatus.BOOKED)
	payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
	payment_reference = models.CharField(max_length=64, blank=True)
	special_requests = models.TextField(blank=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['reference_number']),
			models.Index(fields=['check_in', 'check_out']),
		]

	def clean(self):
		if self.check_in >= self.check_out:
			raise ValidationError('Check-out date must be after check-in date.')
		if self.check_in < timezone.now().date():
			raise ValidationError('Check-in date must be in the future.')

	@property
	def nights(self) -> int:
		return (self.check_out - self.check_in).days

	def __str__(self):  # pragma: no cover
		return f"Hotel booking {self.reference_number}"
