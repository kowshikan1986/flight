"""Forms for car rental."""

from __future__ import annotations

from datetime import date

from django import forms

from .models import Car
from .services import check_availability


class CarSearchForm(forms.Form):
    pickup_location = forms.CharField(max_length=255)
    dropoff_location = forms.CharField(max_length=255)
    pickup_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    dropoff_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pickup_location'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Pick-up location'
        })
        self.fields['dropoff_location'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Drop-off location'
        })
        date_attrs = {'class': 'form-control form-control-lg'}
        self.fields['pickup_date'].widget.attrs.update(date_attrs | {'placeholder': 'Pick-up date'})
        self.fields['dropoff_date'].widget.attrs.update(date_attrs | {'placeholder': 'Drop-off date'})

    def clean(self):
        cleaned_data = super().clean()
        pickup_date = cleaned_data.get('pickup_date')
        dropoff_date = cleaned_data.get('dropoff_date')
        if pickup_date and pickup_date < date.today():
            raise forms.ValidationError('Pick-up date must be in the future')
        if pickup_date and dropoff_date and dropoff_date <= pickup_date:
            raise forms.ValidationError('Drop-off date must be after pick-up date')
        return cleaned_data


class CarBookingForm(forms.Form):
    car_id = forms.IntegerField(widget=forms.HiddenInput)
    pickup_location = forms.CharField(max_length=255)
    dropoff_location = forms.CharField(max_length=255)
    pickup_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    dropoff_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    contact_email = forms.EmailField()
    payment_token = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        text_fields = ['pickup_location', 'dropoff_location', 'contact_email']
        for field in text_fields:
            self.fields[field].widget.attrs.update({'class': 'form-control', 'placeholder': field.replace('_', ' ').title()})
        for field in ['pickup_date', 'dropoff_date']:
            self.fields[field].widget.attrs.update({'class': 'form-control', 'placeholder': field.replace('_', ' ').title()})

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
        if isinstance(car, Car) and pickup_date and dropoff_date:
            availability = check_availability(car, pickup_date, dropoff_date)
            if not availability.available:
                raise forms.ValidationError(availability.reasons)
        return cleaned_data
