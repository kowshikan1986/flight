"""Flight search and booking views."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Any, Iterable

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, TemplateView

from core.models import AvailabilityError

from .forms import FlightPassengerDetailsForm, FlightPaymentForm, FlightSearchForm
from .models import Flight, FlightBooking, FlightSeat
from .services import (
    HAND_LUGGAGE_LIMIT_KG,
    OVERWEIGHT_INCLUDED_KG,
    calculate_luggage_overweight_fee,
    create_booking,
    normalize_weight_input,
    search_flights,
)

logger = logging.getLogger(__name__)

SUPPORTED_CURRENCY = getattr(
    settings,
    'FLIGHT_BOOKING_CURRENCY',
    getattr(settings, 'DEFAULT_CURRENCY', 'USD'),
)


def normalize_airport(value: str | None) -> str:
    if not value:
        return ''
    normalized = ' '.join(str(value).strip().split())
    return normalized.upper()


def _airport_aliases(value: str | None) -> set[str]:
    normalized = normalize_airport(value)
    if not normalized:
        return set()
    variants: set[str] = {normalized}
    if '(' in normalized and ')' in normalized:
        prefix, _, suffix = normalized.partition('(')
        airport_code = suffix.rstrip(')').strip()
        prefix_value = prefix.strip()
        if prefix_value:
            variants.add(prefix_value)
        if airport_code:
            variants.add(airport_code)
    else:
        parts = normalized.split()
        if parts:
            variants.add(parts[0])
    return {alias for alias in variants if alias}


def airports_match(first: str | None, second: str | None) -> bool:
    if not first and not second:
        return True
    first_aliases = _airport_aliases(first)
    second_aliases = _airport_aliases(second)
    if not first_aliases or not second_aliases:
        return normalize_airport(first) == normalize_airport(second)
    return bool(first_aliases & second_aliases)


def build_return_identifier(code: str | None, departure: datetime | None) -> str:
    code_part = (code or '').strip()
    if not departure:
        return code_part
    departure_value = departure
    if timezone.is_naive(departure_value):
        departure_value = timezone.make_aware(departure_value, timezone=timezone.get_current_timezone())
    return f'{code_part}|{departure_value.isoformat()}'


def parse_return_identifier(identifier: str) -> tuple[str | None, datetime | None]:
    if not identifier:
        return None, None
    code_part, _, departure_part = identifier.partition('|')
    code_value = code_part.strip() or None
    if not departure_part:
        return code_value, None
    try:
        parsed_departure = datetime.fromisoformat(departure_part)
    except ValueError:
        return code_value, None
    if timezone.is_naive(parsed_departure):
        parsed_departure = timezone.make_aware(parsed_departure, timezone=timezone.get_current_timezone())
    return code_value, parsed_departure


def collect_return_options(
    *,
    return_origin: str,
    return_destination: str,
    return_date: datetime,
    passenger_count: int,
) -> list[dict[str, Any]]:
    normalized_return_origin = normalize_airport(return_origin)
    normalized_return_destination = normalize_airport(return_destination)

    current_timezone = timezone.get_current_timezone()
    base_departure = return_date
    if timezone.is_naive(base_departure):
        base_departure = timezone.make_aware(base_departure, timezone=current_timezone)
    else:
        base_departure = base_departure.astimezone(current_timezone)

    requested_return_date = base_departure.date()
    options: list[dict[str, Any]] = []
    seen_identifiers: set[str] = set()

    def append_option(
        *,
        code: str,
        origin: str | None,
        destination: str | None,
        departure: datetime | None,
        arrival: datetime | None,
        fare: Decimal | None,
        seats_available: int | None,
        fallback_capacity: int | None,
        is_alternate_date: bool,
    ) -> None:
        if departure is None:
            return
        departure_value = departure
        if timezone.is_naive(departure_value):
            departure_value = timezone.make_aware(departure_value, timezone=current_timezone)
        arrival_value = arrival
        if isinstance(arrival_value, datetime) and timezone.is_naive(arrival_value):
            arrival_value = timezone.make_aware(arrival_value, timezone=current_timezone)

        identifier = build_return_identifier(code, departure_value)
        if identifier in seen_identifiers:
            return
        effective_capacity = seats_available
        if effective_capacity is None or effective_capacity <= 0:
            effective_capacity = fallback_capacity
        if (
            effective_capacity is not None
            and passenger_count > 0
            and effective_capacity < passenger_count
        ):
            return

        display_capacity = effective_capacity

        options.append(
            {
                'code': code,
                'origin': origin,
                'destination': destination,
                'departure': departure_value,
                'arrival': arrival_value,
                'fare': fare,
                'seats_available': display_capacity,
                'is_alternate_date': is_alternate_date,
                'alternate_date': departure_value.date(),
                'requested_return_date': requested_return_date,
                'identifier': identifier,
            }
        )
        seen_identifiers.add(identifier)

    flights_with_return_legs = (
        Flight.objects.filter(
            return_departure_time__isnull=False,
            return_departure_time__gte=base_departure,
            is_active=True,
        )
        .order_by('return_departure_time')
    )

    for flight in flights_with_return_legs:
        departure_time = flight.return_departure_time
        if departure_time is None:
            continue
        if normalized_return_origin:
            flight_return_origin = getattr(flight, 'return_origin', '')
            if not airports_match(flight_return_origin, return_origin):
                continue
        if normalized_return_destination:
            flight_return_destination = getattr(flight, 'return_destination', '')
            if not airports_match(flight_return_destination, return_destination):
                continue

        seats_available = getattr(flight, 'available_return_seats', None)
        fare_component = getattr(flight, 'return_base_price', None)
        if fare_component is None:
            fare_component = Decimal('0.00')
        append_option(
            code=getattr(flight, 'return_code', None) or flight.code,
            origin=getattr(flight, 'return_origin', None) or return_origin,
            destination=getattr(flight, 'return_destination', None) or return_destination,
            departure=departure_time,
            arrival=getattr(flight, 'return_arrival_time', None),
            fare=fare_component,
            seats_available=seats_available,
            fallback_capacity=getattr(flight, 'seat_capacity', None),
            is_alternate_date=departure_time.date() != requested_return_date,
        )

    lookahead_days = max(0, getattr(settings, 'FLIGHT_RETURN_LOOKAHEAD_DAYS', 14))
    for offset in range(0, lookahead_days + 1):
        candidate_date = requested_return_date + timedelta(days=offset)
        if candidate_date < timezone.localdate():
            continue
        candidate_departure = datetime.combine(candidate_date, datetime.min.time())
        candidate_departure = timezone.make_aware(candidate_departure, timezone=current_timezone)
        matching_flights = search_flights(
            origin=return_origin,
            destination=return_destination,
            departure_date=candidate_departure,
            passenger_count=passenger_count,
        )
        for flight in matching_flights:
            seats_available = getattr(flight, 'available_seat_count', None)
            if seats_available is None:
                seats_available = getattr(flight, 'available_seats', None)
            append_option(
                code=flight.code,
                origin=flight.origin,
                destination=flight.destination,
                departure=flight.departure_time,
                arrival=flight.arrival_time,
                fare=flight.base_price,
                seats_available=seats_available,
                fallback_capacity=getattr(flight, 'seat_capacity', None),
                is_alternate_date=candidate_date != requested_return_date,
            )

    now_value = timezone.now()
    options.sort(
        key=lambda option: (
            option.get('departure') is None,
            option.get('departure') or now_value,
            option.get('fare') is None,
            option.get('fare'),
        )
    )
    return options


def match_return_option(identifier: str, options: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if not identifier:
        return None
    match = next((option for option in options if option.get('identifier') == identifier), None)
    if match is not None:
        return dict(match)
    parsed_code, parsed_departure = parse_return_identifier(identifier)
    for option in options:
        code_value = option.get('code')
        if parsed_code and code_value == parsed_code:
            departure_value = option.get('departure')
            if isinstance(parsed_departure, datetime) and isinstance(departure_value, datetime):
                if departure_value.isoformat() == parsed_departure.isoformat():
                    return dict(option)
            elif parsed_departure is None:
                return dict(option)
    return None


def serialize_return_option(option: Mapping[str, Any]) -> dict[str, Any]:
    if not option:
        return {}
    departure_value = option.get('departure')
    arrival_value = option.get('arrival')
    alternate_date_value = option.get('alternate_date')
    requested_value = option.get('requested_return_date')
    fare_value = option.get('fare')
    return {
        'identifier': option.get('identifier', ''),
        'code': option.get('code'),
        'origin': option.get('origin'),
        'destination': option.get('destination'),
        'departure': departure_value.isoformat() if isinstance(departure_value, datetime) else departure_value,
        'arrival': arrival_value.isoformat() if isinstance(arrival_value, datetime) else arrival_value,
        'fare': str(fare_value) if fare_value is not None else None,
        'seats_available': option.get('seats_available'),
        'is_alternate_date': bool(option.get('is_alternate_date')),
        'alternate_date': (
            alternate_date_value.isoformat() if isinstance(alternate_date_value, date) else alternate_date_value
        ),
        'requested_return_date': (
            requested_value.isoformat() if isinstance(requested_value, date) else requested_value
        ),
    }


def deserialize_return_option(data: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None
    departure_value = data.get('departure')
    arrival_value = data.get('arrival')
    alternate_date_value = data.get('alternate_date')
    requested_value = data.get('requested_return_date')
    fare_value = data.get('fare')
    try:
        fare_decimal = Decimal(str(fare_value)) if fare_value not in (None, '') else Decimal('0.00')
    except (ArithmeticError, ValueError):
        fare_decimal = Decimal('0.00')
    selection = {
        'identifier': data.get('identifier', ''),
        'code': data.get('code'),
        'origin': data.get('origin'),
        'destination': data.get('destination'),
        'departure': None,
        'arrival': None,
        'fare': fare_decimal.quantize(Decimal('0.01')),
        'seats_available': data.get('seats_available'),
        'is_alternate_date': bool(data.get('is_alternate_date')),
        'alternate_date': None,
        'requested_return_date': None,
    }
    if isinstance(departure_value, datetime):
        selection['departure'] = departure_value
    elif isinstance(departure_value, str) and departure_value:
        try:
            selection['departure'] = datetime.fromisoformat(departure_value)
        except ValueError:
            selection['departure'] = None
    if isinstance(arrival_value, datetime):
        selection['arrival'] = arrival_value
    elif isinstance(arrival_value, str) and arrival_value:
        try:
            selection['arrival'] = datetime.fromisoformat(arrival_value)
        except ValueError:
            selection['arrival'] = None
    if isinstance(alternate_date_value, date):
        selection['alternate_date'] = alternate_date_value
    elif isinstance(alternate_date_value, str) and alternate_date_value:
        try:
            selection['alternate_date'] = date.fromisoformat(alternate_date_value)
        except ValueError:
            selection['alternate_date'] = None
    if isinstance(requested_value, date):
        selection['requested_return_date'] = requested_value
    elif isinstance(requested_value, str) and requested_value:
        try:
            selection['requested_return_date'] = date.fromisoformat(requested_value)
        except ValueError:
            selection['requested_return_date'] = None
    return selection


def apply_return_option_to_flight(flight: Flight, option: Mapping[str, Any]) -> None:
    if not option:
        return
    departure_value = option.get('departure')
    arrival_value = option.get('arrival')
    fare_value = option.get('fare')
    requested_value = option.get('requested_return_date')
    alternate_date_value = option.get('alternate_date')

    if isinstance(departure_value, str) and departure_value:
        try:
            departure_value = datetime.fromisoformat(departure_value)
        except ValueError:
            departure_value = None
    if isinstance(arrival_value, str) and arrival_value:
        try:
            arrival_value = datetime.fromisoformat(arrival_value)
        except ValueError:
            arrival_value = None
    if isinstance(requested_value, str) and requested_value:
        try:
            requested_value = date.fromisoformat(requested_value)
        except ValueError:
            requested_value = None
    if isinstance(alternate_date_value, str) and alternate_date_value:
        try:
            alternate_date_value = date.fromisoformat(alternate_date_value)
        except ValueError:
            alternate_date_value = None

    setattr(flight, 'return_origin', option.get('origin') or getattr(flight, 'return_origin', ''))
    setattr(flight, 'return_destination', option.get('destination') or getattr(flight, 'return_destination', ''))
    setattr(flight, 'return_departure_time', departure_value if isinstance(departure_value, datetime) else None)
    setattr(flight, 'return_arrival_time', arrival_value if isinstance(arrival_value, datetime) else None)
    if fare_value is not None:
        try:
            fare_decimal = fare_value if isinstance(fare_value, Decimal) else Decimal(str(fare_value))
        except (ArithmeticError, ValueError):
            fare_decimal = Decimal('0.00')
        setattr(flight, 'return_base_price', fare_decimal.quantize(Decimal('0.01')))
    setattr(flight, 'return_flight_code', option.get('code') or getattr(flight, 'return_flight_code', ''))
    setattr(flight, 'return_seats_available', option.get('seats_available'))
    setattr(flight, 'return_is_alternate_date', bool(option.get('is_alternate_date')))
    setattr(flight, 'return_alternate_date', alternate_date_value if isinstance(alternate_date_value, date) else None)
    setattr(flight, 'requested_return_date', requested_value if isinstance(requested_value, date) else getattr(flight, 'requested_return_date', None))
    setattr(flight, 'selected_return_option_identifier', option.get('identifier'))
    setattr(flight, 'display_return_info', True)



def _booking_session_key(flight_id: int) -> str:
    return f'flight_booking_{flight_id}'


def _coerce_passenger_count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 1
    return max(1, min(7, count))


def _pad_passenger_details(
    passenger_details: Sequence[Mapping[str, Any]] | None,
    passenger_count: int,
) -> list[dict[str, Any]]:
    padded: list[dict[str, Any]] = []
    for idx in range(passenger_count):
        detail: Mapping[str, Any] | None = None
        if passenger_details and idx < len(passenger_details):
            detail = passenger_details[idx]
        detail = detail or {}
        date_of_birth = detail.get('date_of_birth') or ''
        if isinstance(date_of_birth, datetime):
            date_of_birth = date_of_birth.date().isoformat()
        elif isinstance(date_of_birth, date):
            date_of_birth = date_of_birth.isoformat()
        padded.append({
            'first_name': (detail.get('first_name') or '').strip(),
            'last_name': (detail.get('last_name') or '').strip(),
            'contact_number': (detail.get('contact_number') or '').strip(),
            'date_of_birth': date_of_birth,
            'main_luggage_weight': str(detail.get('main_luggage_weight', '0')),
            'hand_luggage_weight': str(detail.get('hand_luggage_weight', '0')),
            'luggage_fee': str(detail.get('luggage_fee', '0.00')),
        })
    return padded


def _compute_booking_pricing(
    *,
    flight: Flight,
    passenger_count: int,
    passenger_details: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    passenger_count = _coerce_passenger_count(passenger_count)
    seats_qs = (
        flight.seats.filter(is_reserved=False, leg=FlightSeat.Leg.OUTBOUND)
        .order_by('seat_number')
    )
    seats = list(seats_qs[:passenger_count])
    available_outbound = seats_qs.count()

    return_component = (flight.return_base_price or Decimal('0.00')).quantize(Decimal('0.01'))
    fare_breakdown: list[dict[str, Any]] = []
    base_total = Decimal('0.00')
    for idx in range(passenger_count):
        seat = seats[idx] if idx < len(seats) else None
        seat_modifier = seat.price_modifier if seat else Decimal('1.00')
        seat_price = (flight.base_price * seat_modifier).quantize(Decimal('0.01'))
        per_passenger_total = seat_price + return_component
        detail_bits: list[str] = []
        if seat:
            detail_bits.append(f'Seat {seat.seat_number}')
            try:
                detail_bits.append(seat.get_seat_class_display())
            except AttributeError:
                pass
        if return_component > Decimal('0.00'):
            detail_bits.append(f'Return fare ${return_component}')
        fare_breakdown.append({
            'label': f'Passenger {idx + 1} fare',
            'detail': ' · '.join(detail_bits) if detail_bits else '',
            'price': per_passenger_total,
        })
        base_total += per_passenger_total

    padded_details = _pad_passenger_details(passenger_details, passenger_count)
    luggage_summary: list[dict[str, Any]] = []
    passenger_luggage: list[dict[str, Any]] = []
    luggage_total = Decimal('0.00')
    for idx, detail in enumerate(padded_details, start=1):
        main_weight = normalize_weight_input(detail.get('main_luggage_weight'))
        hand_weight = normalize_weight_input(detail.get('hand_luggage_weight'))
        luggage_fee = calculate_luggage_overweight_fee(main_weight)
        overweight = main_weight - OVERWEIGHT_INCLUDED_KG
        chargeable_overweight_kg = 0
        if overweight > 0:
            chargeable_overweight_kg = int(overweight.to_integral_value(rounding=ROUND_CEILING))
        luggage_summary.append({
            'index': idx,
            'main_weight': main_weight,
            'hand_weight': hand_weight,
            'luggage_fee': luggage_fee,
            'chargeable_overweight_kg': chargeable_overweight_kg,
        })
        passenger_luggage.append({
            'detail': detail,
            'luggage': luggage_summary[-1],
        })
        luggage_total += luggage_fee

    estimated_total = (base_total + luggage_total).quantize(Decimal('0.01'))
    fare_allocation_warning = (len(seats) < passenger_count) or (available_outbound <= passenger_count)

    return {
        'return_component': return_component,
        'fare_breakdown': fare_breakdown,
        'luggage_summary': luggage_summary,
        'passenger_luggage': passenger_luggage,
        'estimated_total': estimated_total,
        'base_total': base_total,
        'luggage_total': luggage_total,
        'fare_allocation_warning': fare_allocation_warning,
        'padded_details': padded_details,
    }


def _build_booking_context(
    *,
    flight: Flight,
    passenger_count: int,
    passenger_details: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    pricing = _compute_booking_pricing(
        flight=flight,
        passenger_count=passenger_count,
        passenger_details=passenger_details,
    )
    has_return_leg = all(
        [
            flight.return_departure_time,
            flight.return_origin,
            flight.return_destination,
        ]
    )
    return {
        'flight': flight,
        'passenger_count': passenger_count,
        'has_return_leg': bool(has_return_leg),
        'return_route': (
            f'{flight.return_origin} → {flight.return_destination}'
            if has_return_leg
            else ''
        ),
        'return_departure_time': flight.return_departure_time,
        'return_arrival_time': flight.return_arrival_time,
        'return_fare': pricing['return_component'],
        'return_is_alternate_date': bool(getattr(flight, 'return_is_alternate_date', False)),
        'return_alternate_date': getattr(flight, 'return_alternate_date', None),
        'requested_return_date': getattr(flight, 'requested_return_date', None),
        'selected_return_option_identifier': getattr(flight, 'selected_return_option_identifier', None),
        'return_flight_code': getattr(flight, 'return_flight_code', ''),
        'return_seats_available': getattr(flight, 'return_seats_available', None),
        'estimated_total': pricing['estimated_total'],
        'fare_breakdown': pricing['fare_breakdown'],
        'luggage_summary': pricing['luggage_summary'],
        'passenger_luggage': pricing['passenger_luggage'],
        'fare_allocation_warning': pricing['fare_allocation_warning'],
        'included_luggage_allowance': OVERWEIGHT_INCLUDED_KG,
        'carry_on_limit': HAND_LUGGAGE_LIMIT_KG,
        'currency_code': SUPPORTED_CURRENCY,
    }


class BookingSessionMixin:
    flight: Flight

    def get_booking_session_key(self) -> str:
        return _booking_session_key(self.flight.id)

    def load_booking_session_data(self) -> dict[str, Any] | None:
        data = self.request.session.get(self.get_booking_session_key())
        return data if isinstance(data, dict) else None

    def store_booking_session_data(self, data: Mapping[str, Any]) -> None:
        self.request.session[self.get_booking_session_key()] = dict(data)
        self.request.session.modified = True

    def clear_booking_session_data(self) -> None:
        key = self.get_booking_session_key()
        if key in self.request.session:
            del self.request.session[key]
            self.request.session.modified = True

    def update_booking_session_data(self, updates: Mapping[str, Any]) -> dict[str, Any]:
        current = self.load_booking_session_data() or {}
        current.update(updates)
        self.store_booking_session_data(current)
        return current

    def get_return_selection_from_session(self) -> dict[str, Any] | None:
        data = self.load_booking_session_data()
        raw_selection = data.get('return_selection') if data else None
        return deserialize_return_option(raw_selection)

    def apply_session_return_selection(self, flight: Flight) -> dict[str, Any] | None:
        selection = self.get_return_selection_from_session()
        if selection:
            apply_return_option_to_flight(flight, selection)
        return selection


class FlightSearchView(FormView):
    template_name = 'flights/search.html'
    form_class = FlightSearchForm

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        if self.request.method == 'GET' and self.request.GET:
            kwargs['data'] = self.request.GET
        return kwargs

    def build_context(self, form: FlightSearchForm) -> dict[str, Any]:
        results: Iterable[Flight] | None = None
        passenger_count_value = 1
        round_trip_requested = False
        no_results_for_query = False
        selected_return_option = (self.request.GET.get('return_option') or '').strip() or None

        if form.is_valid():
            data = form.cleaned_data
            passenger_count = max(1, min(7, data.get('passenger_count') or 1))
            passenger_count_value = passenger_count

            origin = data['origin']
            destination = data['destination']
            departure_date = datetime.combine(data['departure_date'], datetime.min.time())

            round_trip_requested = bool(data.get('round_trip'))
            return_origin = (data.get('return_origin') or '').strip() or None
            return_destination = (data.get('return_destination') or '').strip() or None
            return_date_value = data.get('return_date') if round_trip_requested else None
            return_departure_dt = (
                datetime.combine(return_date_value, datetime.min.time())
                if round_trip_requested and return_date_value
                else None
            )

            results = list(
                search_flights(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    passenger_count=passenger_count,
                )
            )

            return_options: Sequence[dict[str, Any]] = []
            if (
                round_trip_requested
                and return_origin
                and return_destination
                and return_departure_dt is not None
            ):
                return_options = collect_return_options(
                    return_origin=return_origin,
                    return_destination=return_destination,
                    return_date=return_departure_dt,
                    passenger_count=passenger_count,
                )

            for index, flight in enumerate(results):
                self._decorate_flight(
                    flight=flight,
                    passenger_count=passenger_count,
                    round_trip_requested=round_trip_requested,
                    return_options=return_options,
                    return_origin=return_origin,
                    return_destination=return_destination,
                    return_date=return_date_value,
                    assignment_index=index,
                    selected_return_option=selected_return_option,
                )

            no_results_for_query = len(results) == 0
        else:
            if form.is_bound and form.errors:
                for error_list in form.errors.values():
                    for error in error_list:
                        messages.error(self.request, error)
            value = form.data.get('passenger_count')
            try:
                passenger_count_value = int(value)
            except (TypeError, ValueError):
                passenger_count_value = 1

        return self.get_context_data(
            form=form,
            results=results,
            passenger_count=max(1, min(7, passenger_count_value)),
            round_trip_selected=round_trip_requested,
            no_results_for_query=no_results_for_query,
        )

    def _decorate_flight(
        self,
        *,
        flight: Flight,
        passenger_count: int,
        round_trip_requested: bool,
        return_options: Sequence[dict[str, Any]],
        return_origin: str | None,
        return_destination: str | None,
        return_date: date | None,
        assignment_index: int,
        selected_return_option: str | None,
    ) -> None:
        base_price_component = (flight.base_price or Decimal('0.00')).quantize(Decimal('0.01'))
        return_info: dict[str, Any] | None = None
        available_return_options: list[dict[str, Any]] = list(return_options)
        setattr(flight, 'requested_return_date', return_date)

        if round_trip_requested:
            normalized_return_origin = normalize_airport(return_origin)
            normalized_return_destination = normalize_airport(return_destination)
            requested_return_date = return_date
            if all(
                [
                    flight.return_departure_time,
                    flight.return_origin,
                    flight.return_destination,
                ]
            ):
                route_matches = (
                    normalized_return_origin
                    and normalized_return_destination
                    and airports_match(flight.return_origin, return_origin)
                    and airports_match(flight.return_destination, return_destination)
                )
                date_matches = (
                    requested_return_date is None
                    or (
                        flight.return_departure_time
                        and flight.return_departure_time.date() == requested_return_date
                    )
                )
                if route_matches and date_matches:
                    return_info = {
                        'code': getattr(flight, 'return_code', None) or flight.code,
                        'origin': flight.return_origin,
                        'destination': flight.return_destination,
                        'departure': flight.return_departure_time,
                        'arrival': getattr(flight, 'return_arrival_time', None),
                        'fare': getattr(flight, 'return_base_price', Decimal('0.00')),
                        'seats_available': getattr(flight, 'available_return_seats', None),
                        'is_alternate_date': False,
                        'alternate_date': requested_return_date,
                        'identifier': build_return_identifier(
                            getattr(flight, 'return_code', None) or flight.code,
                            flight.return_departure_time,
                        ),
                    }
                    available_return_options = [return_info] + [
                        option
                        for option in available_return_options
                        if option.get('identifier') != return_info['identifier']
                    ]

            if available_return_options:
                setattr(flight, 'selected_return_option_identifier', selected_return_option)
                match = None
                if selected_return_option:
                    match = next(
                        (
                            option
                            for option in available_return_options
                            if option.get('identifier') == selected_return_option
                        ),
                        None,
                    )
                    if match is None:
                        parsed_code, parsed_departure = parse_return_identifier(selected_return_option)
                        for option in available_return_options:
                            code_match = bool(parsed_code) and option.get('code') == parsed_code
                            if not code_match:
                                continue
                            departure_value = option.get('departure')
                            if isinstance(parsed_departure, datetime) and isinstance(departure_value, datetime):
                                if departure_value.isoformat() == parsed_departure.isoformat():
                                    match = option
                                    break
                            elif parsed_departure is None:
                                match = option
                                break
                if match is not None:
                    return_info = match
                elif return_info is None:
                    option_index = assignment_index % len(available_return_options)
                    return_info = available_return_options[option_index]

        return_component = Decimal('0.00')
        has_return_leg = False
        outbound_seats_available = getattr(flight, 'available_seat_count', None)
        if outbound_seats_available is None:
            try:
                outbound_seats_available = flight.available_seats
            except AttributeError:
                outbound_seats_available = None

        if return_info is not None:
            fare_value = return_info.get('fare') or Decimal('0.00')
            return_component = fare_value.quantize(Decimal('0.01'))
            has_return_leg = True
            setattr(flight, 'return_route', f"{return_info['origin']} -> {return_info['destination']}")
            setattr(flight, 'return_departure_display', return_info['departure'])
            setattr(flight, 'return_arrival_display', return_info.get('arrival'))
            setattr(flight, 'return_fare', return_component)
            setattr(flight, 'return_flight_code', return_info.get('code', ''))
            setattr(flight, 'display_return_info', True)
            setattr(
                flight,
                'additional_return_options',
                [
                    option
                    for option in available_return_options
                    if option.get('identifier') != return_info.get('identifier')
                ],
            )
            setattr(flight, 'return_options', available_return_options)
            setattr(
                flight,
                'return_seats_available',
                return_info.get('seats_available'),
            )
            setattr(flight, 'return_is_alternate_date', bool(return_info.get('is_alternate_date')))
            setattr(flight, 'selected_return_option_identifier', return_info.get('identifier'))
        else:
            setattr(flight, 'return_route', '')
            setattr(flight, 'return_departure_display', None)
            setattr(flight, 'return_arrival_display', None)
            setattr(flight, 'return_fare', Decimal('0.00'))
            setattr(flight, 'return_flight_code', '')
            setattr(flight, 'display_return_info', False)
            setattr(flight, 'additional_return_options', [])
            setattr(flight, 'return_options', [])
            setattr(flight, 'return_seats_available', None)
            setattr(flight, 'return_is_alternate_date', False)
            setattr(flight, 'selected_return_option_identifier', None)

        setattr(flight, 'has_return_leg', has_return_leg)
        setattr(flight, 'requested_passenger_count', passenger_count)
        setattr(flight, 'outbound_seats_available', outbound_seats_available)
        setattr(
            flight,
            'available_seat_label',
            outbound_seats_available,
        )
        total_per_passenger = (base_price_component + return_component).quantize(Decimal('0.01'))
        setattr(flight, 'estimated_total_price', total_per_passenger * passenger_count)

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        form = self.get_form()
        return self.render_to_response(self.build_context(form))

    def form_valid(self, form: FlightSearchForm) -> HttpResponse:
        return self.render_to_response(self.build_context(form))

    def form_invalid(self, form: FlightSearchForm) -> HttpResponse:
        return self.render_to_response(self.build_context(form))


class FlightDetailView(DetailView):
    template_name = 'flights/detail.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'

    def get_queryset(self):  # pragma: no cover - thin wrapper
        return (
            Flight.objects.filter(is_active=True)
            .prefetch_related('seats')
        )


class FlightBookingListView(LoginRequiredMixin, ListView):
    template_name = 'flights/booking_list.html'
    context_object_name = 'bookings'

    def get_queryset(self):  # pragma: no cover - trivial wrapper
        return (
            FlightBooking.objects.filter(user=self.request.user)
            .select_related('flight')
            .prefetch_related('seats')
            .order_by('-created_at')
        )


class FlightBookingDetailView(LoginRequiredMixin, DetailView):
    template_name = 'flights/booking_detail.html'
    slug_field = 'reference_number'
    slug_url_kwarg = 'reference'

    def get_queryset(self):  # pragma: no cover - trivial wrapper
        return (
            FlightBooking.objects.filter(user=self.request.user)
            .select_related('flight')
            .prefetch_related('seats', 'flightbookingseat_set__seat')
        )


class FlightBookingCreateView(LoginRequiredMixin, BookingSessionMixin, FormView):
    template_name = 'flights/book.html'
    form_class = FlightPassengerDetailsForm

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.flight = get_object_or_404(
            Flight.objects.filter(is_active=True),
            id=kwargs.get('flight_id'),
        )
        self.return_selection = self._initialise_return_selection()
        return super().dispatch(request, *args, **kwargs)

    def get_passenger_count(self) -> int:
        if self.request.method == 'POST':
            source = self.request.POST.get('passenger_count')
        else:
            source = self.request.GET.get('passengers')
            if source is None:
                session_data = self.load_booking_session_data()
                if session_data:
                    source = session_data.get('passenger_count')
        return _coerce_passenger_count(source)

    def get_initial(self) -> dict[str, Any]:
        initial = super().get_initial()
        session_data = self.load_booking_session_data()
        if session_data:
            initial['contact_email'] = session_data.get('contact_email', '')
            initial['notify_admin'] = session_data.get('notify_admin', True)
            for idx, detail in enumerate(session_data.get('passenger_details', [])):
                prefix = f'passenger_{idx}'
                initial[f'{prefix}_first_name'] = detail.get('first_name', '')
                initial[f'{prefix}_last_name'] = detail.get('last_name', '')
                initial[f'{prefix}_contact_number'] = detail.get('contact_number', '')
                initial[f'{prefix}_date_of_birth'] = detail.get('date_of_birth', '')
                initial[f'{prefix}_main_luggage_weight'] = detail.get('main_luggage_weight', '0')
                initial[f'{prefix}_hand_luggage_weight'] = detail.get('hand_luggage_weight', '0')
        return initial

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs['flight'] = self.flight
        kwargs['passenger_count'] = self.get_passenger_count()
        return kwargs

    def _initialise_return_selection(self) -> dict[str, Any] | None:
        selection_identifier = (self.request.GET.get('return_option') or '').strip()
        selection: dict[str, Any] | None = None
        requested_return_date: date | None = None

        if selection_identifier:
            passenger_count = self.get_passenger_count()
            return_origin = (self.request.GET.get('return_origin') or '').strip()
            return_destination = (self.request.GET.get('return_destination') or '').strip()
            return_date_value = (self.request.GET.get('return_date') or '').strip()
            if return_date_value:
                try:
                    requested_return_date = date.fromisoformat(return_date_value)
                except ValueError:
                    requested_return_date = None

            return_departure_dt: datetime | None = None
            if requested_return_date is not None:
                return_departure_dt = datetime.combine(requested_return_date, datetime.min.time())

            flight_return_departure = getattr(self.flight, 'return_departure_time', None)
            if return_departure_dt is None and isinstance(flight_return_departure, datetime):
                return_departure_dt = flight_return_departure
                requested_return_date = requested_return_date or flight_return_departure.date()

            if not return_origin:
                return_origin = getattr(self.flight, 'return_origin', '') or ''
            if not return_destination:
                return_destination = getattr(self.flight, 'return_destination', '') or ''

            options: list[dict[str, Any]] = []
            if return_origin and return_destination and isinstance(return_departure_dt, datetime):
                options = collect_return_options(
                    return_origin=return_origin,
                    return_destination=return_destination,
                    return_date=return_departure_dt,
                    passenger_count=passenger_count,
                )

            if options:
                selection = match_return_option(selection_identifier, options)

            if selection is None and isinstance(flight_return_departure, datetime):
                fallback_option = {
                    'identifier': build_return_identifier(
                        getattr(self.flight, 'return_code', None) or self.flight.code,
                        flight_return_departure,
                    ),
                    'code': getattr(self.flight, 'return_code', None) or self.flight.code,
                    'origin': getattr(self.flight, 'return_origin', None),
                    'destination': getattr(self.flight, 'return_destination', None),
                    'departure': flight_return_departure,
                    'arrival': getattr(self.flight, 'return_arrival_time', None),
                    'fare': getattr(self.flight, 'return_base_price', Decimal('0.00')),
                    'seats_available': getattr(self.flight, 'available_return_seats', None),
                    'is_alternate_date': False,
                    'alternate_date': flight_return_departure.date(),
                    'requested_return_date': requested_return_date,
                }
                selection = match_return_option(selection_identifier, [fallback_option])

            if selection is not None and selection.get('requested_return_date') is None:
                selection['requested_return_date'] = requested_return_date

        if selection is not None:
            self.update_booking_session_data({'return_selection': serialize_return_option(selection)})
            apply_return_option_to_flight(self.flight, selection)
            return selection

        session_selection = self.get_return_selection_from_session()
        if session_selection:
            apply_return_option_to_flight(self.flight, session_selection)
        return session_selection

    def _extract_passenger_details_from_request(self) -> list[dict[str, Any]]:
        passenger_count = self.get_passenger_count()
        details: list[dict[str, Any]] = []
        for idx in range(passenger_count):
            prefix = f'passenger_{idx}'
            main_weight = normalize_weight_input(self.request.POST.get(f'{prefix}_main_luggage_weight'))
            hand_weight = normalize_weight_input(self.request.POST.get(f'{prefix}_hand_luggage_weight'))
            details.append({
                'first_name': self.request.POST.get(f'{prefix}_first_name', ''),
                'last_name': self.request.POST.get(f'{prefix}_last_name', ''),
                'contact_number': self.request.POST.get(f'{prefix}_contact_number', ''),
                'date_of_birth': self.request.POST.get(f'{prefix}_date_of_birth', ''),
                'main_luggage_weight': str(main_weight),
                'hand_luggage_weight': str(hand_weight),
                'luggage_fee': str(calculate_luggage_overweight_fee(main_weight)),
            })
        return details

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        passenger_count = self.get_passenger_count()
        passenger_details: Sequence[Mapping[str, Any]] | None = None
        form: FlightPassengerDetailsForm = context.get('form')
        if form is not None and form.is_bound:
            if form.is_valid():
                passenger_details = form.get_passenger_details()
            else:
                passenger_details = self._extract_passenger_details_from_request()
        else:
            session_data = self.load_booking_session_data()
            if session_data:
                passenger_details = session_data.get('passenger_details')

        context.update(
            _build_booking_context(
                flight=self.flight,
                passenger_count=passenger_count,
                passenger_details=passenger_details,
            )
        )
        if getattr(self, 'return_selection', None):
            context.setdefault('return_selection', self.return_selection)
        context.setdefault('support_email', getattr(settings, 'DEFAULT_FROM_EMAIL', ''))
        return context

    def form_valid(self, form: FlightPassengerDetailsForm) -> HttpResponse:
        passenger_details = form.get_passenger_details()
        updates = {
            'passenger_count': form.cleaned_data['passenger_count'],
            'contact_email': form.cleaned_data['contact_email'],
            'notify_admin': bool(form.cleaned_data.get('notify_admin')),
            'passenger_details': passenger_details,
        }
        self.update_booking_session_data(updates)
        return redirect('flights:book-review', self.flight.id)

    def form_invalid(self, form: FlightPassengerDetailsForm) -> HttpResponse:
        return self.render_to_response(self.get_context_data(form=form))


class FlightBookingReviewView(LoginRequiredMixin, BookingSessionMixin, TemplateView):
    template_name = 'flights/book_review.html'

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.flight = get_object_or_404(
            Flight.objects.filter(is_active=True),
            id=kwargs.get('flight_id'),
        )
        self.booking_data = self.load_booking_session_data()
        if not self.booking_data:
            messages.info(request, 'Please complete passenger details before reviewing your booking.')
            return redirect('flights:book', self.flight.id)
        self.return_selection = self.apply_session_return_selection(self.flight)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        passenger_count = _coerce_passenger_count(self.booking_data.get('passenger_count'))
        context.update(
            _build_booking_context(
                flight=self.flight,
                passenger_count=passenger_count,
                passenger_details=self.booking_data.get('passenger_details'),
            )
        )
        context['booking_data'] = self.booking_data
        if getattr(self, 'return_selection', None):
            context.setdefault('return_selection', self.return_selection)
        return context

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return redirect('flights:book-payment', self.flight.id)


class FlightBookingPaymentView(LoginRequiredMixin, BookingSessionMixin, FormView):
    template_name = 'flights/book_payment.html'
    form_class = FlightPaymentForm

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.flight = get_object_or_404(
            Flight.objects.filter(is_active=True),
            id=kwargs.get('flight_id'),
        )
        self.booking_data = self.load_booking_session_data()
        if not self.booking_data:
            messages.info(request, 'Your booking session expired. Please restart the booking flow.')
            return redirect('flights:book', self.flight.id)
        self.return_selection = self.apply_session_return_selection(self.flight)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        passenger_count = _coerce_passenger_count(self.booking_data.get('passenger_count'))
        context.update(
            _build_booking_context(
                flight=self.flight,
                passenger_count=passenger_count,
                passenger_details=self.booking_data.get('passenger_details'),
            )
        )
        context['booking_data'] = self.booking_data
        context['stripe_publishable_key'] = getattr(settings, 'STRIPE_PUBLISHABLE_KEY', '')
        if getattr(self, 'return_selection', None):
            context.setdefault('return_selection', self.return_selection)
        return context

    def form_valid(self, form: FlightPaymentForm) -> HttpResponse:
        if getattr(self, 'return_selection', None) is None:
            self.return_selection = self.apply_session_return_selection(self.flight)
        passenger_count = _coerce_passenger_count(self.booking_data.get('passenger_count'))
        passenger_details_raw = self.booking_data.get('passenger_details') or []
        prepared_passengers: list[dict[str, Any]] = []
        for detail in passenger_details_raw:
            dob_value = detail.get('date_of_birth')
            dob: date | None = None
            if isinstance(dob_value, date):
                dob = dob_value
            elif isinstance(dob_value, str) and dob_value:
                try:
                    dob = date.fromisoformat(dob_value)
                except ValueError:
                    dob = None
            prepared_passengers.append({
                'first_name': (detail.get('first_name') or '').strip(),
                'last_name': (detail.get('last_name') or '').strip(),
                'contact_number': (detail.get('contact_number') or '').strip(),
                'date_of_birth': dob,
                'main_luggage_weight': normalize_weight_input(detail.get('main_luggage_weight')),
                'hand_luggage_weight': normalize_weight_input(detail.get('hand_luggage_weight')),
            })

        payment_token = form.cleaned_data.get('payment_token') or None

        try:
            booking = create_booking(
                user=self.request.user,
                flight=self.flight,
                contact_email=self.booking_data.get('contact_email', '').strip(),
                notify_admin=bool(self.booking_data.get('notify_admin', True)),
                payment_token=payment_token,
                passenger_count=passenger_count,
                passenger_details=prepared_passengers,
            )
        except AvailabilityError as exc:
            logger.warning('Flight booking availability error: %s', exc)
            messages.error(
                self.request,
                'Seats were just taken. Please review availability and try again.',
            )
            return redirect('flights:book', self.flight.id)
        except Exception:
            logger.exception('Unexpected failure while confirming flight booking')
            messages.error(
                self.request,
                'We could not process your booking payment. Please try again.',
            )
            return self.render_to_response(self.get_context_data(form=form))

        self.clear_booking_session_data()
        messages.success(
            self.request,
            f'Flight booking confirmed. Reference {booking.reference_number}.',
        )
        return redirect('flights:booking-detail', booking.reference_number)

    def form_invalid(self, form: FlightPaymentForm) -> HttpResponse:
        return self.render_to_response(self.get_context_data(form=form))
