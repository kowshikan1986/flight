"""Domain services for hotel availability and bookings."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction

from core.models import AvailabilityError, daterange, send_booking_email
from payments.services import charge_booking, store_payment_record

from .models import HotelBooking, HotelRoomInventory, HotelRoomType

logger = logging.getLogger(__name__)


@dataclass
class HotelAvailability:
    room_type: HotelRoomType
    check_in: date
    check_out: date
    rooms_requested: int
    available: bool
    reasons: list[str]


def _ensure_inventory(room_type: HotelRoomType, inventory_date: date) -> HotelRoomInventory:
    inventory, _ = HotelRoomInventory.objects.get_or_create(
        room_type=room_type,
        date=inventory_date,
        defaults={'available_rooms': room_type.total_rooms},
    )
    if inventory.available_rooms > room_type.total_rooms:
        inventory.available_rooms = room_type.total_rooms
        inventory.save(update_fields=['available_rooms'])
    return inventory


def check_availability(room_type: HotelRoomType, check_in: date, check_out: date, rooms: int = 1) -> HotelAvailability:
    if check_in >= check_out:
        return HotelAvailability(room_type, check_in, check_out, rooms, False, ['Invalid date range'])

    reasons: list[str] = []
    for night in daterange(check_in, check_out):
        inventory = _ensure_inventory(room_type, night)
        if inventory.available_rooms < rooms:
            reasons.append(f"Only {inventory.available_rooms} rooms left on {night:%Y-%m-%d}")
    return HotelAvailability(room_type, check_in, check_out, rooms, not reasons, reasons)


def calculate_total_price(room_type: HotelRoomType, check_in: date, check_out: date, rooms: int = 1) -> Decimal:
    nights = (check_out - check_in).days
    return room_type.base_price * Decimal(nights) * Decimal(rooms)


def _adjust_inventory(room_type: HotelRoomType, check_in: date, check_out: date, rooms: int, delta: int) -> None:
    for night in daterange(check_in, check_out):
        inventory = _ensure_inventory(room_type, night)
        new_value = inventory.available_rooms + delta * rooms
        if new_value < 0:
            raise AvailabilityError({'inventory': f'Insufficient rooms available for {night:%Y-%m-%d}'})
        inventory.available_rooms = new_value
        inventory.save(update_fields=['available_rooms'])


def reserve_inventory(room_type: HotelRoomType, check_in: date, check_out: date, rooms: int) -> None:
    logger.debug("Reserving %s rooms for %s (%s to %s)", rooms, room_type, check_in, check_out)
    _adjust_inventory(room_type, check_in, check_out, rooms, delta=-1)


def release_inventory(room_type: HotelRoomType, check_in: date, check_out: date, rooms: int) -> None:
    logger.debug("Releasing %s rooms for %s (%s to %s)", rooms, room_type, check_in, check_out)
    _adjust_inventory(room_type, check_in, check_out, rooms, delta=1)


def create_booking(
    *,
    user,
    room_type: HotelRoomType,
    check_in: date,
    check_out: date,
    rooms: int,
    guests: int,
    surname: str,
    contact_email: str,
    special_requests: str = '',
    payment_token: str | None = None,
) -> HotelBooking:
    availability = check_availability(room_type, check_in, check_out, rooms)
    if not availability.available:
        raise AvailabilityError({'rooms': availability.reasons})

    total_price = calculate_total_price(room_type, check_in, check_out, rooms)

    with transaction.atomic():
        reserve_inventory(room_type, check_in, check_out, rooms)
        try:
            payment = charge_booking(
                user=user,
                amount=total_price,
                currency='usd',
                description=f'Hotel booking for {room_type.hotel.name}',
                metadata={
                    'booking_type': 'hotel',
                    'hotel': str(room_type.hotel.id),
                    'room_type': room_type.get_room_type_display(),
                    'check_in': check_in.isoformat(),
                    'check_out': check_out.isoformat(),
                },
                payment_token=payment_token,
            )
        except Exception:  # pragma: no cover - provider-specific
            logger.exception('Payment failed for hotel booking')
            release_inventory(room_type, check_in, check_out, rooms)
            raise

        booking = HotelBooking.objects.create(
            user=user,
            room_type=room_type,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            surname=surname,
            contact_email=contact_email,
            total_price=total_price,
            payment_status=(
                HotelBooking.PaymentStatus.SETTLED
                if payment.is_success
                else HotelBooking.PaymentStatus.PENDING
            ),
            payment_reference=payment.reference,
            special_requests=special_requests,
        )

        store_payment_record(
            user=user,
            content_object=booking,
            amount=total_price,
            currency='usd',
            result=payment,
        )

    send_booking_email(
        subject='Hotel booking confirmation',
        message=(
            f'Dear {surname},\n\n'
            f'Your reservation at {room_type.hotel.name} from {check_in:%Y-%m-%d} '
            f'to {check_out:%Y-%m-%d} has been confirmed. '
            f'Your booking reference is {booking.reference_number}.'
        ),
        recipient_list=[contact_email],
    )

    return booking