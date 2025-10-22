"""Flight domain models."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from core.models import ReferenceNumberMixin, TimeStampedModel


class Flight(TimeStampedModel):
	code = models.CharField(max_length=10, unique=True)
	origin = models.CharField(max_length=120)
	destination = models.CharField(max_length=120)
	departure_time = models.DateTimeField()
	arrival_time = models.DateTimeField()
	return_departure_time = models.DateTimeField(blank=True, null=True)
	return_arrival_time = models.DateTimeField(blank=True, null=True)
	return_code = models.CharField(max_length=10, blank=True)
	return_origin = models.CharField(max_length=120, blank=True)
	return_destination = models.CharField(max_length=120, blank=True)
	return_base_price = models.DecimalField(max_digits=9, decimal_places=2, default=Decimal('0.00'))
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
		return_fields = [
			self.return_code.strip() if self.return_code else '',
			self.return_departure_time,
			self.return_arrival_time,
			self.return_origin.strip() if self.return_origin else '',
			self.return_destination.strip() if self.return_destination else '',
		]
		has_return_values = any(return_fields)
		if has_return_values:
			missing: list[str] = []
			if not (self.return_code or '').strip():
				missing.append('return_code')
			if self.return_departure_time is None:
				missing.append('return_departure_time')
			if self.return_arrival_time is None:
				missing.append('return_arrival_time')
			if not (self.return_origin or '').strip():
				missing.append('return_origin')
			if not (self.return_destination or '').strip():
				missing.append('return_destination')
			if missing:
				errors.update({field: 'All return flight details must be provided together.' for field in missing})
			elif self.return_departure_time and self.return_arrival_time and self.return_departure_time >= self.return_arrival_time:
				errors['return_arrival_time'] = 'Return arrival must be after return departure.'
		elif (self.return_departure_time is None) != (self.return_arrival_time is None):
			errors['return_departure_time'] = 'Both return departure and arrival must be provided together.'
			errors['return_arrival_time'] = 'Both return departure and arrival must be provided together.'

		if self.return_base_price is not None and self.return_base_price < 0:
			errors['return_base_price'] = 'Return fare cannot be negative.'
		if errors:
			raise ValidationError(errors)

	def __str__(self):  # pragma: no cover
		return f"{self.code}: {self.origin} → {self.destination}"

	@property
	def available_seats(self) -> int:
		return self.seats.filter(is_reserved=False, leg=FlightSeat.Leg.OUTBOUND).count()

	@property
	def available_return_seats(self) -> int:
		return self.seats.filter(is_reserved=False, leg=FlightSeat.Leg.RETURN).count()


class SeatClass(models.TextChoices):
	ECONOMY = 'economy', 'Economy'
	PREMIUM = 'premium', 'Premium Economy'
	BUSINESS = 'business', 'Business'
	FIRST = 'first', 'First Class'


class FlightSeat(TimeStampedModel):
	class Leg(models.TextChoices):
		OUTBOUND = 'outbound', 'Outbound'
		RETURN = 'return', 'Return'

	flight = models.ForeignKey(Flight, related_name='seats', on_delete=models.CASCADE)
	leg = models.CharField(max_length=8, choices=Leg.choices, default=Leg.OUTBOUND)
	seat_number = models.CharField(max_length=5)
	seat_class = models.CharField(max_length=20, choices=SeatClass.choices)
	price_modifier = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.0'))
	is_reserved = models.BooleanField(default=False)

	class Meta:
		unique_together = ('flight', 'leg', 'seat_number')
		ordering = ['leg', 'seat_number']

	def __str__(self):  # pragma: no cover
		leg_label = self.get_leg_display()
		return f"{self.flight.code} {leg_label} seat {self.seat_number}"


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
	main_luggage_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
	hand_luggage_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
	luggage_fee = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0.00'))

	class Meta:
		unique_together = ('booking', 'seat')

	def __str__(self):  # pragma: no cover
		return f"{self.booking.reference_number} -> {self.seat.seat_number}"


Flight.available_seats.fget.short_description = 'Available seats'
Flight.available_return_seats.fget.short_description = 'Return seats available'
