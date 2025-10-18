"""Core site-wide views."""

from __future__ import annotations

from typing import Any

from django.views.generic import TemplateView

from cars.forms import CarSearchForm
from flights.forms import FlightSearchForm
from hotels.forms import HotelSearchForm


class HomeView(TemplateView):
	template_name = 'home.html'

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context.setdefault('hotel_search_form', HotelSearchForm())
		context.setdefault('flight_search_form', FlightSearchForm())
		context.setdefault('car_search_form', CarSearchForm())
		return context
