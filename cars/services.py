"""Car rental booking services."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction

from core.models import AvailabilityError, daterange, send_booking_email
from payments.services import charge_booking, store_payment_record

from .models import Car, CarAvailability, CarBooking

logger = logging.getLogger(__name__)


@dataclass
class CarAvailabilityResult:
    car: Car
    pickup_date: date
    dropoff_date: date
    available: bool
    reasons: list[str]


def ensure_availability_record(car: Car, day: date) -> CarAvailability:
    availability, _ = CarAvailability.objects.get_or_create(car=car, date=day)
    return availability


def check_availability(car: Car, pickup_date: date, dropoff_date: date) -> CarAvailabilityResult:
    reasons: list[str] = []
    if pickup_date >= dropoff_date:
        reasons.append('Drop-off date must be after pick-up date')
    for day in daterange(pickup_date, dropoff_date):
        availability = ensure_availability_record(car, day)
        if not availability.is_available:
            reasons.append(f'Car unavailable on {day:%Y-%m-%d}')
    return CarAvailabilityResult(car=car, pickup_date=pickup_date, dropoff_date=dropoff_date, available=not reasons, reasons=reasons)


def mark_availability(car: Car, pickup_date: date, dropoff_date: date, is_available: bool) -> None:
    for day in daterange(pickup_date, dropoff_date):
        availability = ensure_availability_record(car, day)
        availability.is_available = is_available
        availability.save(update_fields=['is_available'])


def calculate_total_price(car: Car, pickup_date: date, dropoff_date: date) -> Decimal:
    rental_days = (dropoff_date - pickup_date).days
    return car.price_per_day * Decimal(rental_days)


def create_booking(
    *,
    user,
    car: Car,
    pickup_location: str,
    dropoff_location: str,
    pickup_date: date,
    dropoff_date: date,
    contact_email: str,
    payment_token: str | None = None,
) -> CarBooking:
    availability = check_availability(car, pickup_date, dropoff_date)
    if not availability.available:
        raise AvailabilityError({'car': availability.reasons})

    total_price = calculate_total_price(car, pickup_date, dropoff_date)

    with transaction.atomic():
        mark_availability(car, pickup_date, dropoff_date, False)
        try:
            payment = charge_booking(
                user=user,
                amount=total_price,
                currency='usd',
                description=f'Car rental for {car.company} {car.model}',
                metadata={
                    'booking_type': 'car',
                    'car_id': str(car.id),
                    'pickup_location': pickup_location,
                    'dropoff_location': dropoff_location,
                },
                payment_token=payment_token,
            )
        except Exception:
            logger.exception('Payment failed for car booking')
            mark_availability(car, pickup_date, dropoff_date, True)
            raise

        booking = CarBooking.objects.create(
            user=user,
            car=car,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_date=pickup_date,
            dropoff_date=dropoff_date,
            total_price=total_price,
            payment_status=(
                CarBooking.PaymentStatus.SETTLED
                if payment.is_success
                else CarBooking.PaymentStatus.PENDING
            ),
            payment_reference=payment.reference,
            contact_email=contact_email,
        )

        store_payment_record(
            user=user,
            content_object=booking,
            amount=total_price,
            currency='usd',
            result=payment,
        )

    send_booking_email(
        subject='Car rental confirmation',
        message=(
            f'Your car rental for {car.company} {car.model} is confirmed from {pickup_date:%Y-%m-%d} '
            f'to {dropoff_date:%Y-%m-%d}. Reference: {booking.reference_number}.'
        ),
        recipient_list=[contact_email],
    )

    return booking
