"""Car rental views."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView, ListView

from core.models import AvailabilityError

from .forms import CarBookingForm, CarSearchForm
from .models import Car, CarBooking
from .services import create_booking


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
		if form.is_valid():
			data = form.cleaned_data
			results = Car.objects.filter(
				location__icontains=data['pickup_location'],
				is_active=True,
			).order_by('company', 'model')
		return self.get_context_data(form=form, results=results)

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


class CarBookingCreateView(LoginRequiredMixin, FormView):
	template_name = 'cars/book.html'
	form_class = CarBookingForm
	success_url = reverse_lazy('cars:booking-list')

	def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		self.car = get_object_or_404(Car, pk=self.kwargs['car_id'])
		return super().dispatch(request, *args, **kwargs)

	def get_initial(self) -> dict[str, Any]:
		initial = super().get_initial()
		initial.update({'car_id': self.car.id, 'pickup_location': self.car.location})
		if self.request.GET.get('pickup_date'):
			initial['pickup_date'] = self.request.GET['pickup_date']
		if self.request.GET.get('dropoff_date'):
			initial['dropoff_date'] = self.request.GET['dropoff_date']
		return initial

	def get_form_kwargs(self) -> dict[str, Any]:
		kwargs = super().get_form_kwargs()
		if self.request.method == 'POST':
			kwargs['data'] = self.request.POST
		return kwargs

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context['car'] = self.car
		return context

	def form_valid(self, form: CarBookingForm) -> HttpResponse:
		car: Car = form.cleaned_data['car_id']
		try:
			booking = create_booking(
				user=self.request.user,
				car=car,
				pickup_location=form.cleaned_data['pickup_location'],
				dropoff_location=form.cleaned_data['dropoff_location'],
				pickup_date=form.cleaned_data['pickup_date'],
				dropoff_date=form.cleaned_data['dropoff_date'],
				contact_email=form.cleaned_data['contact_email'],
				payment_token=form.cleaned_data.get('payment_token'),
			)
		except AvailabilityError as exc:
			form.add_error(None, exc.messages)
			return self.form_invalid(form)

		messages.success(self.request, 'Car rental confirmed!')
		return redirect('cars:booking-detail', reference=booking.reference_number)


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
