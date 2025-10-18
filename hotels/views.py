"""Views for hotel search and booking."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView, ListView

from core.models import AvailabilityError

from .forms import HotelBookingForm, HotelSearchForm
from .models import Hotel, HotelBooking, HotelRoomType
from .services import create_booking


class HotelsEnabledMixin:
	"""Mixin that disables hotel views when the feature flag is off."""

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:  # type: ignore[override]
		if not getattr(settings, "FEATURE_HOTELS_ENABLED", True):
			raise Http404()
		return super().dispatch(request, *args, **kwargs)


class HotelSearchView(HotelsEnabledMixin, FormView):
	template_name = 'hotels/search.html'
	form_class = HotelSearchForm

	def get_form_kwargs(self) -> dict[str, Any]:
		kwargs = super().get_form_kwargs()
		if self.request.method == 'GET' and self.request.GET:
			kwargs['data'] = self.request.GET
		return kwargs

	def build_context(self, form: HotelSearchForm) -> dict[str, Any]:
		results: Iterable[HotelRoomType] | None = None
		check_in = check_out = None
		if form.is_valid():
			location = form.cleaned_data['location']
			check_in = form.cleaned_data['check_in']
			check_out = form.cleaned_data['check_out']
			room_type = form.cleaned_data['room_type']
			results = (
				HotelRoomType.objects
				.select_related('hotel')
				.filter(
					hotel__location__icontains=location,
					room_type=room_type,
					hotel__is_active=True,
				)
			)
		return self.get_context_data(form=form, results=results, check_in=check_in, check_out=check_out)

	def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		form = self.get_form()
		return self.render_to_response(self.build_context(form))

	def form_valid(self, form: HotelSearchForm) -> HttpResponse:
		return self.render_to_response(self.build_context(form))

	def form_invalid(self, form: HotelSearchForm) -> HttpResponse:
		return self.render_to_response(self.build_context(form))

	def get_initial(self) -> dict[str, Any]:
		today = date.today()
		return {
			'check_in': today,
			'check_out': today + timedelta(days=1),
		}


class HotelDetailView(HotelsEnabledMixin, DetailView):
	template_name = 'hotels/detail.html'
	model = Hotel
	slug_field = 'slug'
	slug_url_kwarg = 'slug'

	def get_queryset(self):  # type: ignore[override]
		return (
			Hotel.objects.filter(is_active=True)
			.prefetch_related(Prefetch('room_types', queryset=HotelRoomType.objects.order_by('room_type')))
		)


class HotelBookingCreateView(HotelsEnabledMixin, LoginRequiredMixin, FormView):
	template_name = 'hotels/book.html'
	form_class = HotelBookingForm

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		self.room_type = get_object_or_404(HotelRoomType, id=self.kwargs['room_type_id'])
		return super().dispatch(request, *args, **kwargs)

	def get_initial(self) -> dict[str, Any]:
		initial = super().get_initial()
		initial.update(
			{
				'room_type_id': self.room_type.id,
				'check_in': self.request.GET.get('check_in'),
				'check_out': self.request.GET.get('check_out'),
			}
		)
		return initial

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['room_type'] = self.room_type
		return context

	def form_valid(self, form: HotelBookingForm) -> HttpResponse:
		try:
			booking = create_booking(
				user=self.request.user,
				room_type=form.cleaned_data['room_type'],
				check_in=form.cleaned_data['check_in'],
				check_out=form.cleaned_data['check_out'],
				rooms=form.cleaned_data['rooms'],
				guests=form.cleaned_data['guests'],
				surname=form.cleaned_data['surname'],
				contact_email=form.cleaned_data['contact_email'],
				special_requests=form.cleaned_data.get('special_requests', ''),
				payment_token=form.cleaned_data.get('payment_token'),
			)
		except AvailabilityError as exc:
			form.add_error(None, exc.messages)
			return self.form_invalid(form)

		messages.success(self.request, 'Your hotel booking has been confirmed!')
		return redirect('hotels:booking-detail', reference=booking.reference_number)


class HotelBookingListView(HotelsEnabledMixin, LoginRequiredMixin, ListView):
	template_name = 'hotels/booking_list.html'
	model = HotelBooking
	context_object_name = 'bookings'

	def get_queryset(self):  # type: ignore[override]
		return (
			HotelBooking.objects
			.filter(user=self.request.user)
			.select_related('room_type__hotel')
			.order_by('-created_at')
		)


class HotelBookingDetailView(HotelsEnabledMixin, LoginRequiredMixin, DetailView):
	template_name = 'hotels/booking_detail.html'
	slug_field = 'reference_number'
	slug_url_kwarg = 'reference'
	model = HotelBooking

	def get_queryset(self):  # type: ignore[override]
		return (
			HotelBooking.objects
			.filter(user=self.request.user)
			.select_related('room_type__hotel')
		)
