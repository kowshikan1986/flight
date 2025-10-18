"""Flight booking services."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

from django.db import transaction
from django.db.models import Prefetch, Count, Q

from core.models import AvailabilityError, send_booking_email
from payments.services import charge_booking, notify_admins, store_payment_record

from .models import Flight, FlightBooking, FlightBookingSeat, FlightSeat

logger = logging.getLogger(__name__)


@dataclass
class SeatSelection:
    seat_id: int
    seat_number: str
    seat_class: str
    price: Decimal


def search_flights(
    *,
    origin: str,
    destination: str,
    departure_date: datetime,
    return_date: datetime | None = None,
    passenger_count: int = 1,
) -> Iterable[Flight]:
    queryset = (
        Flight.objects.filter(
            origin__icontains=origin,
            destination__icontains=destination,
            departure_time__date=departure_date.date(),
            is_active=True,
        )
        .prefetch_related(Prefetch('seats', queryset=FlightSeat.objects.order_by('seat_number')))
        .annotate(
            available_seat_count=Count('seats', filter=Q(seats__is_reserved=False))
        )
        .filter(available_seat_count__gte=max(1, min(7, passenger_count)))
        .order_by('departure_time')
    )
    if return_date:
        queryset = queryset.filter(return_departure_time__date=return_date.date())
    return queryset


def calculate_total_price(seats: Iterable[FlightSeat], base_price: Decimal) -> Decimal:
    total = Decimal('0.0')
    for seat in seats:
        total += base_price * seat.price_modifier
    return total.quantize(Decimal('0.01'))


def reserve_seats(seats: Iterable[FlightSeat]) -> None:
    for seat in seats:
        if seat.is_reserved:
            raise AvailabilityError({'seat': f'Seat {seat.seat_number} is no longer available'})
        seat.is_reserved = True
        seat.save(update_fields=['is_reserved'])


def release_seats(seats: Iterable[FlightSeat]) -> None:
    for seat in seats:
        seat.is_reserved = False
        seat.save(update_fields=['is_reserved'])


def create_booking(
    *,
    user,
    flight: Flight,
    contact_email: str,
    notify_admin: bool = True,
    payment_token: str | None = None,
    passenger_count: int,
    passenger_details: list[dict[str, Any]] | None = None,
) -> FlightBooking:
    passenger_count = max(1, passenger_count)
    seats = list(
        FlightSeat.objects
        .filter(flight=flight, is_reserved=False)
        .order_by('seat_number')[:passenger_count]
    )
    if len(seats) < passenger_count:
        raise AvailabilityError({'seats': 'Not enough seats remaining for this booking'})

    passenger_detail_list: list[dict[str, Any]] = []
    if passenger_details is not None:
        if len(passenger_details) != len(seats):
            raise AvailabilityError({'passengers': 'Passenger details do not match selected seats'})

        today_value = date.today()
        for index, detail in enumerate(passenger_details, start=1):
            first_name = (detail.get('first_name') or '').strip()
            last_name = (detail.get('last_name') or '').strip()
            dob_value = detail.get('date_of_birth')

            if not first_name or not last_name or dob_value is None:
                raise AvailabilityError({'passengers': f'Passenger {index} details are incomplete.'})

            if isinstance(dob_value, datetime):
                dob_value = dob_value.date()
            elif isinstance(dob_value, str):
                try:
                    dob_value = date.fromisoformat(dob_value)
                except ValueError:
                    raise AvailabilityError({'passengers': f'Passenger {index} date of birth is invalid.'})

            if dob_value > today_value:
                raise AvailabilityError({'passengers': f'Passenger {index} date of birth cannot be in the future.'})

            passenger_detail_list.append({
                'first_name': first_name,
                'last_name': last_name,
                'contact_number': (detail.get('contact_number') or '').strip(),
                'date_of_birth': dob_value,
            })
    else:
        passenger_detail_list = []

    total_price = calculate_total_price(seats, flight.base_price)

    with transaction.atomic():
        reserve_seats(seats)
        try:
            payment = charge_booking(
                user=user,
                amount=total_price,
                currency='usd',
                description=f'Flight booking for {flight.code}',
                metadata={
                    'booking_type': 'flight',
                    'flight': flight.code,
                    'origin': flight.origin,
                    'destination': flight.destination,
                },
                payment_token=payment_token,
            )
        except Exception:
            logger.exception('Payment failed for flight booking')
            release_seats(seats)
            raise

        booking = FlightBooking.objects.create(
            user=user,
            flight=flight,
            passengers=len(seats),
            total_price=total_price,
            payment_status=(
                FlightBooking.PaymentStatus.SETTLED
                if payment.is_success
                else FlightBooking.PaymentStatus.PENDING
            ),
            payment_reference=payment.reference,
            contact_email=contact_email,
            notify_admin=notify_admin,
        )
        booking_seats: list[FlightBookingSeat] = []
        for index, seat in enumerate(seats):
            detail = passenger_detail_list[index] if index < len(passenger_detail_list) else {}
            booking_seats.append(
                FlightBookingSeat(
                    booking=booking,
                    seat=seat,
                    passenger_first_name=detail.get('first_name', ''),
                    passenger_last_name=detail.get('last_name', ''),
                    passenger_contact_number=detail.get('contact_number', ''),
                    passenger_date_of_birth=detail.get('date_of_birth'),
                )
            )

        FlightBookingSeat.objects.bulk_create(booking_seats)

        store_payment_record(
            user=user,
            content_object=booking,
            amount=total_price,
            currency='usd',
            result=payment,
        )

    seat_numbers = ', '.join(seat.seat_number for seat in seats)
    send_booking_email(
        subject='Flight booking confirmation',
        message=(
            f'Your flight {flight.code} from {flight.origin} to {flight.destination} has been booked.\n'
            f'Seat(s): {seat_numbers}. Reference: {booking.reference_number}.'
        ),
        recipient_list=[contact_email],
    )

    if notify_admin:
        notify_admins(
            subject='New flight booking',
            message=f'Booking {booking.reference_number} created for flight {flight.code}.',
        )

    return booking
