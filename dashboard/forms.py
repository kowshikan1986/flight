"""Administrative forms for dashboard."""

from __future__ import annotations

from decimal import Decimal

from django import forms

from cars.models import CarBooking
from flights.models import Flight, FlightBooking
from hotels.models import HotelBooking, HotelRoomType


class HotelRoomTypePricingForm(forms.ModelForm):
	class Meta:
		model = HotelRoomType
		fields = ['base_price', 'total_rooms', 'description']


class FlightPricingForm(forms.ModelForm):
	class Meta:
		model = Flight
		fields = ['base_price', 'seat_capacity', 'is_active']


class BookingStatusForm(forms.ModelForm):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['status'].widget.attrs['class'] = 'form-select'
		if 'payment_status' in self.fields:
			self.fields['payment_status'].widget.attrs['class'] = 'form-select'


class HotelBookingStatusForm(BookingStatusForm):
	class Meta:
		model = HotelBooking
		fields = ['status', 'payment_status']


class FlightBookingStatusForm(BookingStatusForm):
	class Meta:
		model = FlightBooking
		fields = ['status', 'payment_status']


class CarBookingStatusForm(BookingStatusForm):
	class Meta:
		model = CarBooking
		fields = ['status', 'payment_status']
