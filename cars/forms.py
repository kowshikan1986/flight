"""Forms for car rental."""

from __future__ import annotations

from datetime import date, timedelta

from django import forms

from flights.forms import FlightPaymentForm

from .constants import VAN_HIRE_LOCATIONS
from .models import Car
from .services import check_availability


class CarSearchForm(forms.Form):
    pickup_location = forms.ChoiceField(choices=VAN_HIRE_LOCATIONS)
    dropoff_location = forms.ChoiceField(choices=VAN_HIRE_LOCATIONS, required=False)
    pickup_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        select_attrs = {'class': 'w-full p-3 border border-gray-300 rounded-lg focus:outline-none'}
        self.fields['pickup_location'].widget.attrs.update(select_attrs)
        self.fields['dropoff_location'].widget.attrs.update(select_attrs)
        location_choices = list(VAN_HIRE_LOCATIONS)
        self.fields['pickup_location'].choices = [('', 'Select pick-up location')] + location_choices
        self.fields['dropoff_location'].choices = [('', 'Same as pick-up')] + location_choices
        date_attrs = {'class': 'w-full p-3 border border-gray-300 rounded-lg focus:outline-none'}
        self.fields['pickup_date'].widget.attrs.update(date_attrs | {'placeholder': 'Pick-up date'})

    def clean(self):
        cleaned_data = super().clean()
        pickup_location = cleaned_data.get('pickup_location')
        dropoff_location = cleaned_data.get('dropoff_location')
        cleaned_data['effective_dropoff_location'] = dropoff_location or pickup_location

        pickup_date = cleaned_data.get('pickup_date')
        if pickup_date and pickup_date < date.today():
            raise forms.ValidationError('Pick-up date must be in the future')
        if pickup_date:
            cleaned_data['dropoff_date'] = pickup_date + timedelta(days=1)
        return cleaned_data


class CarBookingForm(forms.Form):
    car_id = forms.IntegerField(widget=forms.HiddenInput)
    pickup_location = forms.CharField(widget=forms.HiddenInput)
    dropoff_location = forms.CharField(widget=forms.HiddenInput)
    pickup_date = forms.DateField(widget=forms.HiddenInput)
    dropoff_date = forms.DateField(widget=forms.HiddenInput)
    pickup_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    first_name = forms.CharField(max_length=80)
    last_name = forms.CharField(max_length=80)
    contact_number = forms.CharField(max_length=40)
    pickup_address = forms.CharField(max_length=255)
    contact_email = forms.EmailField()
    payment_token = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        name_attrs = {'class': 'w-full p-3 border border-gray-300 rounded-lg focus:outline-none', 'placeholder': 'First name'}
        self.fields['first_name'].widget.attrs.update(name_attrs)
        self.fields['last_name'].widget.attrs.update({**name_attrs, 'placeholder': 'Last name'})
        self.fields['contact_number'].widget.attrs.update({
            'class': 'w-full p-3 border border-gray-300 rounded-lg focus:outline-none',
            'placeholder': '+94 77 123 4567',
        })
        self.fields['pickup_address'].widget.attrs.update({
            'class': 'w-full p-3 border border-gray-300 rounded-lg focus:outline-none',
            'placeholder': 'Apartment, street, city',
        })
        self.fields['contact_email'].widget.attrs.update({
            'class': 'w-full p-3 border border-gray-300 rounded-lg focus:outline-none',
            'placeholder': 'your@email.com',
        })
        self.fields['pickup_time'].widget.attrs.update({
            'class': 'w-full p-3 border border-gray-300 rounded-lg focus:outline-none',
            'placeholder': 'Pick-up time',
        })

    def clean_car_id(self):
        car_id = self.cleaned_data['car_id']
        try:
            return Car.objects.get(id=car_id)
        except Car.DoesNotExist as exc:
            raise forms.ValidationError('Selected car is no longer available') from exc

    def clean(self):
        cleaned_data = super().clean()
        car = cleaned_data.get('car_id')
        pickup_date = cleaned_data.get('pickup_date')
        dropoff_date = cleaned_data.get('dropoff_date')
        for field in ['first_name', 'last_name', 'contact_number']:
            if cleaned_data.get(field):
                cleaned_data[field] = cleaned_data[field].strip()
        if cleaned_data.get('pickup_address'):
            cleaned_data['pickup_address'] = cleaned_data['pickup_address'].strip()
        if isinstance(car, Car) and pickup_date and dropoff_date:
            availability = check_availability(car, pickup_date, dropoff_date)
            if not availability.available:
                raise forms.ValidationError(availability.reasons)
        contact_number = cleaned_data.get('contact_number', '')
        if contact_number and len(contact_number) < 6:
            self.add_error('contact_number', 'Enter a valid contact number')
        return cleaned_data


class CarPaymentForm(FlightPaymentForm):
    """Payment form for car bookings (reuses flight payment configuration)."""

