"""Car rental views."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import date, datetime, timedelta, time
from typing import Any, Iterable

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.dateparse import parse_date, parse_time
from django.views.generic import DetailView, FormView, ListView, TemplateView

from core.models import AvailabilityError

from .forms import CarBookingForm, CarPaymentForm, CarSearchForm
from .models import Car, CarBooking
from .services import calculate_total_price, check_availability, create_booking

logger = logging.getLogger(__name__)

SUPPORTED_CURRENCY = getattr(
	settings,
	'CAR_BOOKING_CURRENCY',
	getattr(settings, 'DEFAULT_CURRENCY', 'USD'),
)


def _coerce_date(value: Any) -> date | None:
	if isinstance(value, date) and not isinstance(value, datetime):
		return value
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, str):
		return parse_date(value)
	return None


def _coerce_time(value: Any) -> time | None:
	if isinstance(value, time):
		return value
	if isinstance(value, datetime):
		return value.time()
	if isinstance(value, str):
		return parse_time(value)
	return None


def _clean_str(value: Any) -> str:
	if not value:
		return ''
	return str(value).strip()


def build_booking_summary(car: Car, booking_data: Mapping[str, Any]) -> dict[str, Any]:
	pickup_date = _coerce_date(booking_data.get('pickup_date'))
	if pickup_date is None:
		pickup_date = car.default_pickup_date or date.today()

	dropoff_date = _coerce_date(booking_data.get('dropoff_date'))
	if dropoff_date is None:
		dropoff_date = car.default_dropoff_date or pickup_date + timedelta(days=1)

	pickup_time = _coerce_time(booking_data.get('pickup_time'))

	pickup_location = _clean_str(
		booking_data.get('pickup_location') or car.pickup_location or car.location
	)
	dropoff_location = _clean_str(
		booking_data.get('dropoff_location') or car.dropoff_location or pickup_location
	)

	summary = {
		'pickup_location': pickup_location,
		'dropoff_location': dropoff_location,
		'pickup_date': pickup_date,
		'dropoff_date': dropoff_date,
		'pickup_time': pickup_time,
		'pickup_address': _clean_str(booking_data.get('pickup_address')),
		'first_name': _clean_str(booking_data.get('first_name')),
		'last_name': _clean_str(booking_data.get('last_name')),
		'contact_number': _clean_str(booking_data.get('contact_number')),
		'contact_email': _clean_str(booking_data.get('contact_email')),
		'estimated_total': calculate_total_price(car, pickup_date, dropoff_date),
		'currency_code': SUPPORTED_CURRENCY,
	}

	try:
		summary['duration_days'] = max((dropoff_date - pickup_date).days, 1)
	except Exception:  # pragma: no cover - defensive guard
		summary['duration_days'] = 1

	return summary


class CarBookingSessionMixin:
	car: Car

	def get_booking_session_key(self) -> str:
		return f'car_booking_{self.car.id}'

	def load_booking_session_data(self) -> dict[str, Any] | None:
		data = self.request.session.get(self.get_booking_session_key())
		return data if isinstance(data, dict) else None

	def store_booking_session_data(self, data: Mapping[str, Any]) -> None:
		self.request.session[self.get_booking_session_key()] = dict(data)
		self.request.session.modified = True

	def update_booking_session_data(self, updates: Mapping[str, Any]) -> dict[str, Any]:
		current = self.load_booking_session_data() or {}
		current.update(updates)
		self.store_booking_session_data(current)
		return current

	def clear_booking_session_data(self) -> None:
		key = self.get_booking_session_key()
		if key in self.request.session:
			del self.request.session[key]
			self.request.session.modified = True


class CarSearchView(FormView):
	template_name = 'cars/search.html'
	form_class = CarSearchForm

	def get_form_kwargs(self) -> dict[str, Any]:
		kwargs = super().get_form_kwargs()
		if self.request.method == 'GET' and self.request.GET:
			kwargs['data'] = self.request.GET
		return kwargs

	def build_context(self, form: CarSearchForm) -> dict[str, Any]:
		results: Iterable[Car] | None = None
		pickup_date: date | None = None
		dropoff_date: date | None = None
		effective_dropoff = None

		if form.is_valid():
			data = form.cleaned_data
			pickup_date = data['pickup_date']
			dropoff_date = data.get('dropoff_date')
			effective_dropoff = data.get('effective_dropoff_location')

			filters: dict[str, Any] = {
				'pickup_location__iexact': data['pickup_location'],
				'is_active': True,
			}
			if data.get('dropoff_location'):
				filters['dropoff_location__iexact'] = data['dropoff_location']

			candidate_cars = Car.objects.filter(**filters).order_by('company', 'model')
			available_cars: list[Car] = []
			for car in candidate_cars:
				availability = check_availability(car, pickup_date, dropoff_date)
				if availability.available:
					car.estimated_total_price = car.price_per_trip
					available_cars.append(car)
			results = available_cars

		return self.get_context_data(
			form=form,
			results=results,
			search_pickup_date=pickup_date,
			search_dropoff_date=dropoff_date,
			search_pickup_date_str=pickup_date.isoformat() if pickup_date else '',
			search_dropoff_date_str=dropoff_date.isoformat() if dropoff_date else '',
			effective_dropoff=effective_dropoff,
		)

	def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		form = self.get_form()
		return self.render_to_response(self.build_context(form))

	def form_valid(self, form: CarSearchForm) -> HttpResponse:
		return self.render_to_response(self.build_context(form))

	def form_invalid(self, form: CarSearchForm) -> HttpResponse:
		return self.render_to_response(self.build_context(form))


class CarDetailView(DetailView):
	template_name = 'cars/detail.html'
	model = Car

	def get_queryset(self):  # type: ignore[override]
		return Car.objects.filter(is_active=True)


class CarBookingCreateView(LoginRequiredMixin, CarBookingSessionMixin, FormView):
	template_name = 'cars/book.html'
	form_class = CarBookingForm

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		self.car = get_object_or_404(Car, pk=kwargs['car_id'])
		return super().dispatch(request, *args, **kwargs)

	def get_initial(self) -> dict[str, Any]:
		initial = super().get_initial()
		initial.update(
			{
				'car_id': self.car.id,
				'pickup_location': self.car.pickup_location or self.car.location,
				'dropoff_location': self.car.dropoff_location or '',
				'first_name': getattr(self.request.user, 'first_name', ''),
				'last_name': getattr(self.request.user, 'last_name', ''),
				'pickup_address': '',
			}
		)

		if not initial.get('dropoff_location'):
			initial['dropoff_location'] = self.car.pickup_location or self.car.location

		if self.request.GET.get('pickup_date'):
			initial['pickup_date'] = self.request.GET['pickup_date']
		elif self.car.default_pickup_date:
			initial['pickup_date'] = self.car.default_pickup_date

		if self.request.GET.get('dropoff_date'):
			initial['dropoff_date'] = self.request.GET['dropoff_date']
		elif self.car.default_dropoff_date:
			initial['dropoff_date'] = self.car.default_dropoff_date

		if self.request.GET.get('pickup_time'):
			initial['pickup_time'] = self.request.GET['pickup_time']

		session_data = self.load_booking_session_data()
		if session_data:
			pickup_date = _coerce_date(session_data.get('pickup_date'))
			dropoff_date = _coerce_date(session_data.get('dropoff_date'))
			pickup_time = _coerce_time(session_data.get('pickup_time'))

			if pickup_date:
				initial['pickup_date'] = pickup_date
			if dropoff_date:
				initial['dropoff_date'] = dropoff_date
			if pickup_time:
				initial['pickup_time'] = pickup_time

			for field in ['pickup_location', 'dropoff_location', 'pickup_address', 'first_name', 'last_name', 'contact_number', 'contact_email']:
				value = session_data.get(field)
				if value:
					initial[field] = value

		return initial

	def get_form_kwargs(self) -> dict[str, Any]:
		kwargs = super().get_form_kwargs()
		if self.request.method == 'POST':
			kwargs['data'] = self.request.POST
		return kwargs

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		form: CarBookingForm = context['form']

		pickup_date = None
		dropoff_date = None
		if form.is_bound and form.is_valid():
			pickup_date = form.cleaned_data.get('pickup_date')
			dropoff_date = form.cleaned_data.get('dropoff_date')
		else:
			pickup_date = _coerce_date(form.initial.get('pickup_date'))
			dropoff_date = _coerce_date(form.initial.get('dropoff_date'))

		if pickup_date is None:
			pickup_date = self.car.default_pickup_date or date.today()
		if dropoff_date is None:
			dropoff_date = self.car.default_dropoff_date or pickup_date + timedelta(days=1)

		context['car'] = self.car
		context['estimated_total'] = calculate_total_price(self.car, pickup_date, dropoff_date)
		context['currency_code'] = SUPPORTED_CURRENCY
		return context

	def form_valid(self, form: CarBookingForm) -> HttpResponse:
		car: Car = form.cleaned_data['car_id']
		pickup_time = form.cleaned_data.get('pickup_time')

		self.update_booking_session_data(
			{
				'car_id': car.id,
				'pickup_location': _clean_str(form.cleaned_data['pickup_location']),
				'dropoff_location': _clean_str(form.cleaned_data['dropoff_location']) or _clean_str(form.cleaned_data['pickup_location']),
				'pickup_date': form.cleaned_data['pickup_date'].isoformat(),
				'dropoff_date': form.cleaned_data['dropoff_date'].isoformat(),
				'pickup_time': pickup_time.strftime('%H:%M') if pickup_time else '',
				'pickup_address': _clean_str(form.cleaned_data['pickup_address']),
				'first_name': _clean_str(form.cleaned_data['first_name']),
				'last_name': _clean_str(form.cleaned_data['last_name']),
				'contact_number': _clean_str(form.cleaned_data['contact_number']),
				'contact_email': _clean_str(form.cleaned_data['contact_email']),
			}
		)

		return redirect('cars:book-review', car.id)

	def form_invalid(self, form: CarBookingForm) -> HttpResponse:
		return self.render_to_response(self.get_context_data(form=form))


class CarBookingReviewView(LoginRequiredMixin, CarBookingSessionMixin, TemplateView):
	template_name = 'cars/book_review.html'

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		self.car = get_object_or_404(Car, pk=kwargs['car_id'])
		self.booking_data = self.load_booking_session_data()
		if not self.booking_data:
			messages.info(request, 'Please complete hire details before reviewing your booking.')
			return redirect('cars:book', self.car.id)
		self.booking_summary = build_booking_summary(self.car, self.booking_data)
		return super().dispatch(request, *args, **kwargs)

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context.update(
			{
				'car': self.car,
				'booking_data': self.booking_data,
				'booking_summary': self.booking_summary,
			}
		)
		return context

	def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		return redirect('cars:book-payment', self.car.id)


class CarBookingPaymentView(LoginRequiredMixin, CarBookingSessionMixin, FormView):
	template_name = 'cars/book_payment.html'
	form_class = CarPaymentForm

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		self.car = get_object_or_404(Car, pk=kwargs['car_id'])
		self.booking_data = self.load_booking_session_data()
		if not self.booking_data:
			messages.info(request, 'Your booking session expired. Please restart the booking flow.')
			return redirect('cars:book', self.car.id)
		self.booking_summary = build_booking_summary(self.car, self.booking_data)
		return super().dispatch(request, *args, **kwargs)

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context.update(
			{
				'car': self.car,
				'booking_data': self.booking_data,
				'booking_summary': self.booking_summary,
				'stripe_publishable_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
			}
		)
		return context

	def form_valid(self, form: CarPaymentForm) -> HttpResponse:
		summary = self.booking_summary
		pickup_date: date = summary['pickup_date']
		dropoff_date: date = summary['dropoff_date']
		pickup_time: time | None = summary.get('pickup_time')
		payment_token = form.cleaned_data.get('payment_token') or None

		try:
			booking = create_booking(
				user=self.request.user,
				car=self.car,
				pickup_location=summary['pickup_location'],
				dropoff_location=summary['dropoff_location'],
				pickup_date=pickup_date,
				dropoff_date=dropoff_date,
				pickup_time=pickup_time,
				pickup_address=summary['pickup_address'],
				first_name=summary['first_name'],
				last_name=summary['last_name'],
				contact_number=summary['contact_number'],
				contact_email=summary['contact_email'],
				payment_token=payment_token,
			)
		except AvailabilityError as exc:
			logger.warning('Car booking availability error: %s', exc)
			messages.error(
				self.request,
				'This van is no longer available for the selected timeframe. Please choose another slot.',
			)
			self.clear_booking_session_data()
			return redirect('cars:book', self.car.id)
		except Exception:  # pragma: no cover - payment layer failure
			logger.exception('Unexpected failure while confirming car booking')
			messages.error(
				self.request,
				'We could not process your booking payment. Please try again.',
			)
			return self.render_to_response(self.get_context_data(form=form))

		self.clear_booking_session_data()
		messages.success(
			self.request,
			f'Car rental confirmed. Reference {booking.reference_number}.',
		)
		return redirect('cars:booking-detail', reference=booking.reference_number)

	def form_invalid(self, form: CarPaymentForm) -> HttpResponse:
		return self.render_to_response(self.get_context_data(form=form))


class CarBookingListView(LoginRequiredMixin, ListView):
	template_name = 'cars/booking_list.html'
	model = CarBooking
	context_object_name = 'bookings'

	def get_queryset(self):  # type: ignore[override]
		return CarBooking.objects.filter(user=self.request.user).select_related('car').order_by('-created_at')


class CarBookingDetailView(LoginRequiredMixin, DetailView):
	template_name = 'cars/booking_detail.html'
	slug_field = 'reference_number'
	slug_url_kwarg = 'reference'
	model = CarBooking

	def get_queryset(self):  # type: ignore[override]
		return CarBooking.objects.filter(user=self.request.user).select_related('car')
