from __future__ import annotations

from dataclasses import dataclass

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Flight, FlightSeat, SeatClass


@dataclass(frozen=True)
class SeatTemplate:
    number: str
    seat_class: str = SeatClass.ECONOMY
    price_modifier: float = 1.0


DEFAULT_SEATS: tuple[SeatTemplate, ...] = tuple(
    SeatTemplate(number=f"S{i:02d}") for i in range(1, 8)
)


def ensure_seat_inventory(flight: Flight) -> None:
    existing_numbers = set(
        flight.seats.values_list('seat_number', flat=True)
    )
    seats_to_create: list[FlightSeat] = []
    for seat_template in DEFAULT_SEATS:
        if seat_template.number in existing_numbers:
            continue
        seats_to_create.append(
            FlightSeat(
                flight=flight,
                seat_number=seat_template.number,
                seat_class=seat_template.seat_class,
                price_modifier=seat_template.price_modifier,
            )
        )
    if seats_to_create:
        FlightSeat.objects.bulk_create(seats_to_create)


@receiver(post_save, sender=Flight)
def create_default_seats(sender: type[Flight], instance: Flight, created: bool, **kwargs) -> None:
    if created:
        ensure_seat_inventory(instance)
    elif instance.seats.count() < len(DEFAULT_SEATS):
        ensure_seat_inventory(instance)
