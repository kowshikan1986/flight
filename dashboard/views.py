"""Administrative dashboard views."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, UpdateView

from cars.models import CarBooking
from flights.models import Flight, FlightBooking
from hotels.models import HotelBooking, HotelRoomType
from payments.models import Payment

from .forms import (
	CarBookingStatusForm,
	FlightBookingStatusForm,
	FlightPricingForm,
	HotelBookingStatusForm,
	HotelRoomTypePricingForm,
)


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
	raise_exception = True

	def test_func(self) -> bool:  # type: ignore[override]
		return bool(self.request.user.is_staff)


class OverviewView(StaffRequiredMixin, TemplateView):
	template_name = 'dashboard/overview.html'

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['hotel_bookings'] = HotelBooking.objects.count()
		context['flight_bookings'] = FlightBooking.objects.count()
		context['car_bookings'] = CarBooking.objects.count()
		context['total_revenue'] = Payment.objects.filter(status=Payment.Status.SUCCEEDED).aggregate(
			total=Sum('amount')
		)['total'] or Decimal('0.00')
		context['pending_payments'] = Payment.objects.filter(status=Payment.Status.INITIATED).count()
		context['recent_payments'] = Payment.objects.select_related('user').order_by('-created_at')[:10]
		return context


class HotelRoomTypeUpdateView(StaffRequiredMixin, UpdateView):
	model = HotelRoomType
	form_class = HotelRoomTypePricingForm
	template_name = 'dashboard/hotel_pricing_form.html'
	success_url = reverse_lazy('dashboard:hotel-pricing')

	def form_valid(self, form):  # type: ignore[override]
		messages.success(self.request, 'Hotel room pricing updated.')
		return super().form_valid(form)


class HotelPricingListView(StaffRequiredMixin, TemplateView):
	template_name = 'dashboard/hotel_pricing.html'

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['room_types'] = HotelRoomType.objects.select_related('hotel').order_by('hotel__name', 'room_type')
		return context


class FlightPricingUpdateView(StaffRequiredMixin, UpdateView):
	model = Flight
	form_class = FlightPricingForm
	template_name = 'dashboard/flight_pricing_form.html'
	success_url = reverse_lazy('dashboard:flight-pricing')

	def form_valid(self, form):  # type: ignore[override]
		messages.success(self.request, 'Flight pricing updated.')
		return super().form_valid(form)


class FlightPricingListView(StaffRequiredMixin, TemplateView):
	template_name = 'dashboard/flight_pricing.html'

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['flights'] = Flight.objects.order_by('departure_time')
		return context


class BookingManagementView(StaffRequiredMixin, TemplateView):
	template_name = 'dashboard/booking_management.html'

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['hotel_bookings'] = HotelBooking.objects.select_related('room_type__hotel').order_by('-created_at')[:50]
		context['flight_bookings'] = FlightBooking.objects.select_related('flight').order_by('-created_at')[:50]
		context['car_bookings'] = CarBooking.objects.select_related('car').order_by('-created_at')[:50]
		context['hotel_form'] = HotelBookingStatusForm()
		context['flight_form'] = FlightBookingStatusForm()
		context['car_form'] = CarBookingStatusForm()
		return context

	def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		booking_type = request.POST.get('booking_type')
		reference = request.POST.get('reference')
		if not booking_type or not reference:
			messages.error(request, 'Invalid booking update request.')
			return redirect('dashboard:booking-management')

		form_map = {
			'hotel': (HotelBooking, HotelBookingStatusForm),
			'flight': (FlightBooking, FlightBookingStatusForm),
			'car': (CarBooking, CarBookingStatusForm),
		}
		model_class, form_class = form_map.get(booking_type, (None, None))
		if not model_class:
			messages.error(request, 'Unknown booking type.')
			return redirect('dashboard:booking-management')

		booking = get_object_or_404(model_class, reference_number=reference)
		form = form_class(request.POST, instance=booking)
		if form.is_valid():
			form.save()
			messages.success(request, f'{booking_type.title()} booking updated successfully.')
		else:
			messages.error(request, 'Unable to update booking. Please correct the errors.')
		return redirect('dashboard:booking-management')
