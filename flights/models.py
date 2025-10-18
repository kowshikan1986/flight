"""Flight domain models."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import ReferenceNumberMixin, TimeStampedModel


class Flight(TimeStampedModel):
	code = models.CharField(max_length=10, unique=True)
	origin = models.CharField(max_length=120)
	destination = models.CharField(max_length=120)
	departure_time = models.DateTimeField()
	arrival_time = models.DateTimeField()
	return_departure_time = models.DateTimeField(blank=True, null=True)
	return_arrival_time = models.DateTimeField(blank=True, null=True)
	seat_capacity = models.PositiveIntegerField(default=7)
	base_price = models.DecimalField(max_digits=9, decimal_places=2)
	description = models.TextField(blank=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ['departure_time']

	def clean(self):
		errors: dict[str, str] = {}
		if self.seat_capacity != 7:
			errors['seat_capacity'] = 'Seat capacity must remain 7 for standardized inventory.'
		if self.departure_time is not None and self.arrival_time is not None:
			if self.departure_time >= self.arrival_time:
				errors['arrival_time'] = 'Arrival time must be after departure time.'
		if (self.return_departure_time is None) != (self.return_arrival_time is None):
			errors['return_departure_time'] = 'Both return departure and arrival must be provided together.'
			errors['return_arrival_time'] = 'Both return departure and arrival must be provided together.'
		elif self.return_departure_time is not None and self.return_arrival_time is not None:
			if self.return_departure_time >= self.return_arrival_time:
				errors['return_arrival_time'] = 'Return arrival must be after return departure.'
		if errors:
			raise ValidationError(errors)

	def __str__(self):  # pragma: no cover
		return f"{self.code}: {self.origin} → {self.destination}"

	@property
	def available_seats(self) -> int:
		return self.seats.filter(is_reserved=False).count()


class SeatClass(models.TextChoices):
	ECONOMY = 'economy', 'Economy'
	PREMIUM = 'premium', 'Premium Economy'
	BUSINESS = 'business', 'Business'
	FIRST = 'first', 'First Class'


class FlightSeat(TimeStampedModel):
	flight = models.ForeignKey(Flight, related_name='seats', on_delete=models.CASCADE)
	seat_number = models.CharField(max_length=5)
	seat_class = models.CharField(max_length=20, choices=SeatClass.choices)
	price_modifier = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.0'))
	is_reserved = models.BooleanField(default=False)

	class Meta:
		unique_together = ('flight', 'seat_number')
		ordering = ['seat_number']

	def __str__(self):  # pragma: no cover
		return f"{self.flight.code} seat {self.seat_number}"


class FlightBooking(TimeStampedModel, ReferenceNumberMixin):
	class BookingStatus(models.TextChoices):
		BOOKED = 'booked', 'Booked'
		CANCELLED = 'cancelled', 'Cancelled'
		COMPLETED = 'completed', 'Completed'

	class PaymentStatus(models.TextChoices):
		PENDING = 'pending', 'Pending'
		AUTHORIZED = 'authorized', 'Authorized'
		SETTLED = 'settled', 'Settled'
		REFUNDED = 'refunded', 'Refunded'

	user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='flightbookings', on_delete=models.CASCADE)
	flight = models.ForeignKey(Flight, related_name='bookings', on_delete=models.PROTECT)
	seats = models.ManyToManyField(FlightSeat, through='FlightBookingSeat', related_name='seat_bookings')
	passengers = models.PositiveIntegerField(default=1)
	total_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.0'))])
	status = models.CharField(max_length=20, choices=BookingStatus.choices, default=BookingStatus.BOOKED)
	payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
	payment_reference = models.CharField(max_length=64, blank=True)
	contact_email = models.EmailField()
	notify_admin = models.BooleanField(default=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [models.Index(fields=['reference_number'])]

	def __str__(self):  # pragma: no cover
		return f"Flight booking {self.reference_number}"


class FlightBookingSeat(TimeStampedModel):
	booking = models.ForeignKey(FlightBooking, on_delete=models.CASCADE)
	seat = models.ForeignKey(FlightSeat, on_delete=models.CASCADE)
	passenger_first_name = models.CharField(max_length=120, blank=True)
	passenger_last_name = models.CharField(max_length=120, blank=True)
	passenger_contact_number = models.CharField(max_length=32, blank=True)
	passenger_date_of_birth = models.DateField(blank=True, null=True)

	class Meta:
		unique_together = ('booking', 'seat')

	def __str__(self):  # pragma: no cover
		return f"{self.booking.reference_number} -> {self.seat.seat_number}"
