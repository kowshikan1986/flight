"""Flight booking services."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any, Iterable

from django.db import transaction
from django.db.models import Count, Prefetch, Q

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


OVERWEIGHT_INCLUDED_KG = Decimal('40')
HAND_LUGGAGE_LIMIT_KG = Decimal('7')
OVERWEIGHT_FEE_PER_KG = Decimal('20')


def normalize_weight_input(value: Any) -> Decimal:
    if value in (None, ''):
        return Decimal('0.00')
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')
    if decimal_value < 0:
        return Decimal('0.00')
    return decimal_value.quantize(Decimal('0.01'))


def calculate_luggage_overweight_fee(main_luggage_weight: Decimal) -> Decimal:
    overweight = main_luggage_weight - OVERWEIGHT_INCLUDED_KG
    if overweight <= 0:
        return Decimal('0.00')
    chargeable_kg = overweight.to_integral_value(rounding=ROUND_CEILING)
    fee = chargeable_kg * OVERWEIGHT_FEE_PER_KG
    return fee.quantize(Decimal('0.01'))



def _airport_variants(value: str | None) -> set[str]:
    """Return a set of common label variations for an airport string."""
    raw_value = (value or '').strip()
    if not raw_value:
        return set()
    normalized = raw_value.replace(' )', ')')
    normalized = ' '.join(normalized.split())
    variants: set[str] = {raw_value, normalized}
    if ')' in raw_value:
        variants.add(raw_value.replace(')', ' )'))
        variants.add(raw_value.replace(' )', ')'))
    if ')' in normalized:
        variants.add(normalized.replace(')', ' )'))
    return {variant.strip() for variant in variants if variant}


def search_flights(
    *,
    origin: str,
    destination: str,
    departure_date: datetime,
    return_date: datetime | None = None,
    return_origin: str | None = None,
    return_destination: str | None = None,
    passenger_count: int = 1,
) -> Iterable[Flight]:
    outbound_seats_qs = FlightSeat.objects.filter(leg=FlightSeat.Leg.OUTBOUND).order_by('seat_number')
    queryset = (
        Flight.objects.filter(
            departure_time__date=departure_date.date(),
            is_active=True,
        )
        .prefetch_related(Prefetch('seats', queryset=outbound_seats_qs))
        .annotate(
            available_seat_count=Count(
                'seats',
                filter=Q(seats__is_reserved=False, seats__leg=FlightSeat.Leg.OUTBOUND),
            )
        )
        .filter(available_seat_count__gte=max(1, min(7, passenger_count)))
        .order_by('departure_time')
    )
    origin_variants = _airport_variants(origin) or {origin}
    origin_clause = Q()
    for variant in origin_variants:
        origin_clause |= Q(origin__icontains=variant)
    queryset = queryset.filter(origin_clause)
    destination_variants = _airport_variants(destination) or {destination}
    destination_clause = Q()
    for variant in destination_variants:
        destination_clause |= Q(destination__icontains=variant)
    queryset = queryset.filter(destination_clause)
    if return_date:
        return_date_value = return_date.date()
        queryset = queryset.filter(
            Q(return_departure_time__isnull=True)
            | Q(return_departure_time__date__gte=return_date_value)
        )
    if return_origin:
        return_origin_variants = {
            variant for variant in (_airport_variants(return_origin) or {return_origin}) if variant
        }
        if return_origin_variants:
            return_origin_clause = Q(return_origin__isnull=True) | Q(return_origin__exact='')
            for variant in return_origin_variants:
                return_origin_clause |= Q(return_origin__icontains=variant)
            queryset = queryset.filter(return_origin_clause)
    if return_destination:
        return_destination_variants = {
            variant for variant in (_airport_variants(return_destination) or {return_destination}) if variant
        }
        if return_destination_variants:
            return_destination_clause = Q(return_destination__isnull=True) | Q(return_destination__exact='')
            for variant in return_destination_variants:
                return_destination_clause |= Q(return_destination__icontains=variant)
            queryset = queryset.filter(return_destination_clause)
    return queryset


def calculate_total_price(
    seats: Iterable[FlightSeat],
    base_price: Decimal,
    return_base_price: Decimal | None = None,
) -> Decimal:
    total = Decimal('0.0')
    return_component = (return_base_price or Decimal('0.00')).quantize(Decimal('0.01'))
    for seat in seats:
        seat_price = (base_price * seat.price_modifier).quantize(Decimal('0.01'))
        total += seat_price + return_component
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
        .filter(flight=flight, is_reserved=False, leg=FlightSeat.Leg.OUTBOUND)
        .order_by('seat_number')[:passenger_count]
    )
    if len(seats) < passenger_count:
        raise AvailabilityError({'seats': 'Not enough seats remaining for this booking'})

    passenger_detail_list: list[dict[str, Any]] = []
    luggage_fees: list[Decimal] = []
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

            main_weight = normalize_weight_input(detail.get('main_luggage_weight'))
            hand_weight = normalize_weight_input(detail.get('hand_luggage_weight'))
            if hand_weight > HAND_LUGGAGE_LIMIT_KG:
                raise AvailabilityError({'passengers': f'Passenger {index} hand luggage exceeds {HAND_LUGGAGE_LIMIT_KG}kg limit.'})
            luggage_fee = calculate_luggage_overweight_fee(main_weight)
            luggage_fees.append(luggage_fee)

            passenger_detail_list.append({
                'first_name': first_name,
                'last_name': last_name,
                'contact_number': (detail.get('contact_number') or '').strip(),
                'date_of_birth': dob_value,
                'main_luggage_weight': main_weight,
                'hand_luggage_weight': hand_weight,
                'luggage_fee': luggage_fee,
            })
    else:
        passenger_detail_list = []

    return_component = getattr(flight, 'return_base_price', None)
    base_total = calculate_total_price(seats, flight.base_price, return_component)
    luggage_total = sum(luggage_fees, Decimal('0.00')).quantize(Decimal('0.01'))
    total_price = (base_total + luggage_total).quantize(Decimal('0.01'))

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
                    main_luggage_weight=detail.get('main_luggage_weight', Decimal('0.00')),
                    hand_luggage_weight=detail.get('hand_luggage_weight', Decimal('0.00')),
                    luggage_fee=detail.get('luggage_fee', Decimal('0.00')),
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
