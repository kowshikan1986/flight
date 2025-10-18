"""Flight search and booking views."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView, ListView, TemplateView

from core.models import AvailabilityError

from .forms import FlightPassengerDetailsForm, FlightPaymentForm, FlightSearchForm
from .models import Flight, FlightBooking
from .services import calculate_total_price, create_booking, search_flights


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
		if form.is_valid():
			data = form.cleaned_data
			departure_date = datetime.combine(data['departure_date'], datetime.min.time())
			return_date = (
				datetime.combine(data['return_date'], datetime.min.time())
				if data.get('round_trip') and data.get('return_date')
				else None
			)
			passenger_count = data.get('passenger_count') or 1
			passenger_count_value = passenger_count
			results = list(search_flights(
				origin=data['origin'],
				destination=data['destination'],
				departure_date=departure_date,
				return_date=return_date,
				passenger_count=passenger_count,
			))
			for flight in results:
				setattr(flight, 'requested_passenger_count', passenger_count)
				setattr(flight, 'estimated_total_price', flight.base_price * passenger_count)
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
		return self.get_context_data(form=form, results=results, passenger_count=max(1, min(7, passenger_count_value)))

	def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		form = self.get_form()
		return self.render_to_response(self.build_context(form))

	def form_valid(self, form: FlightSearchForm) -> HttpResponse:
		return self.render_to_response(self.build_context(form))

	def form_invalid(self, form: FlightSearchForm) -> HttpResponse:
		return self.render_to_response(self.build_context(form))


class FlightDetailView(DetailView):
	template_name = 'flights/detail.html'
	model = Flight
	slug_field = 'code'
	slug_url_kwarg = 'code'

	def get_queryset(self):  # type: ignore[override]
		return Flight.objects.filter(is_active=True).prefetch_related('seats')


class FlightBookingFlowMixin(LoginRequiredMixin):
	session_namespace = 'flight_booking_flow'

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		self.flight = get_object_or_404(Flight, pk=self.kwargs['flight_id'])
		self.passenger_count = self._determine_passenger_count(request)
		if getattr(self, '_explicit_passenger_count', False):
			stored = self.get_booking_session_data()
			if stored and stored.get('passenger_count') != self.passenger_count:
				self.clear_booking_session_data()
		return super().dispatch(request, *args, **kwargs)

	def _determine_passenger_count(self, request: HttpRequest) -> int:
		default_count = 1
		self._explicit_passenger_count = False
		if request.method == 'POST':
			value = request.POST.get('passenger_count')
		else:
			value = request.GET.get('passengers')
			if value is not None:
				self._explicit_passenger_count = True
			if value is None:
				stored = self.get_booking_session_data()
				if stored:
					value = stored.get('passenger_count')
		try:
			count = int(value) if value is not None else default_count
		except (TypeError, ValueError):
			count = default_count
		return max(1, min(7, count))

	def get_booking_session_key(self) -> str:
		user_identifier = getattr(self.request.user, 'pk', None) or 'anonymous'
		return f'{self.session_namespace}:{user_identifier}:{self.flight.pk}'

	def get_booking_session_data(self) -> dict[str, Any]:
		return self.request.session.get(self.get_booking_session_key(), {})

	def _prepare_session_value(self, value: Any) -> Any:
		if isinstance(value, (date, datetime)):
			return value.isoformat()
		if isinstance(value, Decimal):
			return str(value)
		if isinstance(value, Mapping):
			return {key: self._prepare_session_value(val) for key, val in value.items()}
		if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
			return [self._prepare_session_value(item) for item in value]
		return value

	def save_booking_session_data(self, data: dict[str, Any]) -> None:
		serialized = self._prepare_session_value(data)
		self.request.session[self.get_booking_session_key()] = serialized
		self.request.session.modified = True

	def clear_booking_session_data(self) -> None:
		key = self.get_booking_session_key()
		if key in self.request.session:
			del self.request.session[key]
			self.request.session.modified = True

	def _get_currency_code(self) -> str:
		return getattr(settings, 'BOOKING_CURRENCY', 'USD').upper()

	def _get_pricing_preview(self, passenger_count: int) -> dict[str, Any]:
		count = max(1, passenger_count)
		cache: dict[int, dict[str, Any]] = getattr(self, '_pricing_preview_cache', {})
		if count in cache:
			return cache[count]

		seats = list(self.flight.seats.filter(is_reserved=False).order_by('seat_number')[:count])
		per_passenger: list[dict[str, Any]] = []
		for index, seat in enumerate(seats, start=1):
			seat_price = (self.flight.base_price * seat.price_modifier).quantize(Decimal('0.01'))
			per_passenger.append({
				'index': index,
				'label': f'Passenger {index}',
				'detail': f'Seat {seat.seat_number} · {seat.get_seat_class_display()}',
				'seat_number': seat.seat_number,
				'seat_class': seat.get_seat_class_display(),
				'price': seat_price,
			})

		while len(per_passenger) < count:
			index = len(per_passenger) + 1
			per_passenger.append({
				'index': index,
				'label': f'Passenger {index}',
				'detail': 'Auto-assigned at checkout',
				'seat_number': None,
				'seat_class': None,
				'price': self.flight.base_price.quantize(Decimal('0.01')),
			})

		total = sum((entry['price'] for entry in per_passenger), Decimal('0.00')).quantize(Decimal('0.01'))

		preview = {
			'total': total,
			'breakdown': per_passenger,
			'has_full_allocation': len(seats) >= count,
		}
		cache[count] = preview
		self._pricing_preview_cache = cache
		return preview


class FlightBookingCreateView(FlightBookingFlowMixin, FormView):
	template_name = 'flights/book.html'
	form_class = FlightPassengerDetailsForm

	def get_form_kwargs(self) -> dict[str, Any]:
		kwargs = super().get_form_kwargs()
		kwargs['flight'] = self.flight
		kwargs['passenger_count'] = getattr(self, 'passenger_count', 1)
		if self.request.method == 'POST':
			kwargs['data'] = self.request.POST

		stored = self.get_booking_session_data()
		if stored:
			self.passenger_count = stored.get('passenger_count', self.passenger_count)
			initial = kwargs.get('initial', {}).copy()
			initial.update({
				'contact_email': stored.get('contact_email', ''),
				'notify_admin': stored.get('notify_admin', True),
				'passenger_count': stored.get('passenger_count', self.passenger_count),
			})
			for idx, passenger in enumerate(stored.get('passenger_details', [])):
				initial[f'passenger_{idx}_first_name'] = passenger.get('first_name', '')
				initial[f'passenger_{idx}_last_name'] = passenger.get('last_name', '')
				initial[f'passenger_{idx}_contact_number'] = passenger.get('contact_number', '')
				dob_value = passenger.get('date_of_birth')
				if dob_value:
					initial[f'passenger_{idx}_date_of_birth'] = dob_value
			kwargs['initial'] = initial

		return kwargs

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['flight'] = self.flight
		passenger_count = getattr(self, 'passenger_count', 1)
		pricing_preview = self._get_pricing_preview(passenger_count)
		context['passenger_count'] = passenger_count
		context['estimated_total'] = pricing_preview['total']
		context['fare_breakdown'] = pricing_preview['breakdown']
		context['fare_allocation_warning'] = not pricing_preview['has_full_allocation']
		context['currency_code'] = self._get_currency_code()
		context['booking_step'] = 'passengers'
		return context

	def form_valid(self, form: FlightPassengerDetailsForm) -> HttpResponse:
		booking_data = {
			'flight_id': self.flight.id,
			'passenger_count': form.cleaned_data['passenger_count'],
			'contact_email': form.cleaned_data['contact_email'],
			'notify_admin': form.cleaned_data.get('notify_admin', True),
			'passenger_details': form.get_passenger_details(),
		}
		self.save_booking_session_data(booking_data)
		return redirect('flights:book-review', flight_id=self.flight.id)


class FlightBookingListView(LoginRequiredMixin, ListView):
	template_name = 'flights/booking_list.html'
	model = FlightBooking
	context_object_name = 'bookings'

	def get_queryset(self):  # type: ignore[override]
		return FlightBooking.objects.filter(user=self.request.user).select_related('flight').order_by('-created_at')


class FlightBookingDetailView(LoginRequiredMixin, DetailView):
	template_name = 'flights/booking_detail.html'
	slug_field = 'reference_number'
	slug_url_kwarg = 'reference'
	model = FlightBooking

	def get_queryset(self):  # type: ignore[override]
		return (
			FlightBooking.objects
			.filter(user=self.request.user)
			.select_related('flight')
			.prefetch_related('seats')
		)


class FlightBookingReviewView(FlightBookingFlowMixin, TemplateView):
	template_name = 'flights/book_review.html'

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		response = super().dispatch(request, *args, **kwargs)
		return response

	def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		self.booking_data = self.get_booking_session_data()
		if not self.booking_data:
			messages.info(request, 'Please enter passenger details before reviewing your booking.')
			return redirect('flights:book', flight_id=self.flight.id)
		return super().get(request, *args, **kwargs)

	def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		if not self.get_booking_session_data():
			messages.info(request, 'Your booking session expired. Please re-enter passenger details.')
			return redirect('flights:book', flight_id=self.flight.id)
		return redirect('flights:book-payment', flight_id=self.flight.id)

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		booking_data = self.get_booking_session_data()
		passenger_count = booking_data.get('passenger_count', self.passenger_count)
		pricing_preview = self._get_pricing_preview(passenger_count)
		context.update({
			'flight': self.flight,
			'booking_data': booking_data,
			'passenger_count': passenger_count,
			'estimated_total': pricing_preview['total'],
			'fare_breakdown': pricing_preview['breakdown'],
			'fare_allocation_warning': not pricing_preview['has_full_allocation'],
			'currency_code': self._get_currency_code(),
			'booking_step': 'review',
		})
		return context


class FlightBookingPaymentView(FlightBookingFlowMixin, FormView):
	template_name = 'flights/book_payment.html'
	form_class = FlightPaymentForm

	def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		self.booking_data = self.get_booking_session_data()
		if not self.booking_data:
			messages.info(request, 'Please start your booking before entering payment details.')
			return redirect('flights:book', flight_id=self.kwargs['flight_id'])
		return super().get(request, *args, **kwargs)

	def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		self.booking_data = self.get_booking_session_data()
		if not self.booking_data:
			messages.error(request, 'Your booking session expired. Please restart the booking process.')
			return redirect('flights:book', flight_id=self.kwargs['flight_id'])
		return super().post(request, *args, **kwargs)

	def get_form_kwargs(self) -> dict[str, Any]:
		kwargs = super().get_form_kwargs()
		if self.request.method == 'POST':
			kwargs['data'] = self.request.POST
		return kwargs

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		booking_data = self.get_booking_session_data()
		passenger_count = booking_data.get('passenger_count', self.passenger_count) if booking_data else self.passenger_count
		pricing_preview = self._get_pricing_preview(passenger_count)
		context.update({
			'flight': self.flight,
			'booking_data': booking_data,
			'passenger_count': passenger_count,
			'estimated_total': pricing_preview['total'],
			'fare_breakdown': pricing_preview['breakdown'],
			'fare_allocation_warning': not pricing_preview['has_full_allocation'],
			'currency_code': self._get_currency_code(),
			'booking_step': 'payment',
		})
		return context

	def form_valid(self, form: FlightPaymentForm) -> HttpResponse:
		booking_data = self.get_booking_session_data()
		if not booking_data:
			messages.error(self.request, 'Your booking session expired. Please restart the booking process.')
			return redirect('flights:book', flight_id=self.flight.id)

		try:
			booking = create_booking(
				user=self.request.user,
				flight=self.flight,
				contact_email=booking_data['contact_email'],
				notify_admin=booking_data.get('notify_admin', True),
				payment_token=form.cleaned_data.get('payment_token'),
				passenger_count=booking_data['passenger_count'],
				passenger_details=booking_data.get('passenger_details', []),
			)
		except AvailabilityError as exc:
			form.add_error(None, exc.messages)
			return self.form_invalid(form)

		self.clear_booking_session_data()
		messages.success(self.request, 'Flight booked successfully! A confirmation email has been sent.')
		return redirect('flights:booking-detail', reference=booking.reference_number)
