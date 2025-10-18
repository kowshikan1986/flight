"""Forms for flight search and booking."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django import forms
from django.conf import settings

from .models import Flight, FlightSeat


class FlightSearchForm(forms.Form):
    origin = forms.CharField(max_length=120)
    destination = forms.CharField(max_length=120)
    departure_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    return_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    round_trip = forms.BooleanField(required=False)
    passenger_count = forms.IntegerField(min_value=1, max_value=7, initial=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['origin'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Departure city'
        })
        self.fields['destination'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Arrival city'
        })
        date_attrs = {'class': 'form-control form-control-lg'}
        self.fields['departure_date'].widget.attrs.update(date_attrs | {'placeholder': 'Departure'})
        self.fields['return_date'].widget.attrs.update(date_attrs | {'placeholder': 'Return (optional)'})
        self.fields['round_trip'].widget.attrs.update({'class': 'form-check-input'})
        self.fields['passenger_count'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Passengers',
            'min': 1,
            'max': 7,
        })

    def clean_passenger_count(self) -> int:
        value = self.cleaned_data.get('passenger_count')
        try:
            count = int(value)
        except (TypeError, ValueError):
            count = 1
        return max(1, min(7, count))

    def clean(self):
        cleaned_data = super().clean()
        departure_date = cleaned_data.get('departure_date')
        return_date = cleaned_data.get('return_date')
        today_value = date.today()
        if departure_date and departure_date < today_value:
            self.add_error('departure_date', 'Departure date cannot be in the past.')
        if return_date and return_date < today_value:
            self.add_error('return_date', 'Return date cannot be in the past.')
        if departure_date and return_date and return_date <= departure_date:
            self.add_error('return_date', 'Return date must be after departure date.')
        return cleaned_data


class FlightPassengerDetailsForm(forms.Form):
    flight_id = forms.IntegerField(widget=forms.HiddenInput)
    passenger_count = forms.IntegerField(widget=forms.HiddenInput, min_value=1, max_value=7)
    contact_email = forms.EmailField()
    notify_admin = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        flight: Flight = kwargs.pop('flight')
        passenger_count: int = kwargs.pop('passenger_count', 1)
        super().__init__(*args, **kwargs)
        self.flight = flight
        self.passenger_count = max(1, min(7, passenger_count))
        self.fields['flight_id'].initial = flight.id
        self.fields['passenger_count'].initial = self.passenger_count
        available_seats_qs = flight.seats.filter(is_reserved=False).order_by('seat_number')
        self.available_seats = list(available_seats_qs)
        self.fields['contact_email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Contact email'})
        self.fields['notify_admin'].widget.attrs.update({'class': 'form-check-input'})

        self.passenger_fields: list[dict[str, Any]] = []
        today_value = date.today()
        today_iso = today_value.isoformat()

        for idx in range(self.passenger_count):
            field_prefix = f'passenger_{idx}'
            first_name_field = forms.CharField(max_length=120)
            last_name_field = forms.CharField(max_length=120)
            contact_field = forms.CharField(max_length=32, required=False)
            dob_field = forms.DateField(
                required=True,
                widget=forms.DateInput(attrs={'type': 'date'}),
                error_messages={'required': 'Date of birth is required for each passenger.'},
            )

            first_name_field.label = f'Passenger {idx + 1} first name'
            last_name_field.label = f'Passenger {idx + 1} last name'
            contact_field.label = f'Passenger {idx + 1} contact number'
            dob_field.label = f'Passenger {idx + 1} date of birth'

            self.fields[f'{field_prefix}_first_name'] = first_name_field
            self.fields[f'{field_prefix}_last_name'] = last_name_field
            self.fields[f'{field_prefix}_contact_number'] = contact_field
            self.fields[f'{field_prefix}_date_of_birth'] = dob_field

            first_name_field.widget.attrs.update({'class': 'form-control', 'placeholder': 'First name'})
            last_name_field.widget.attrs.update({'class': 'form-control', 'placeholder': 'Last name'})
            contact_field.widget.attrs.update({'class': 'form-control', 'placeholder': 'Contact number'})
            dob_field.widget.attrs.update({'class': 'form-control', 'max': today_iso})

            self.passenger_fields.append({
                'index': idx + 1,
                'first_name': self[f'{field_prefix}_first_name'],
                'last_name': self[f'{field_prefix}_last_name'],
                'contact_number': self[f'{field_prefix}_contact_number'],
                'date_of_birth': self[f'{field_prefix}_date_of_birth'],
            })

    def clean_passenger_count(self) -> int:
        value = self.cleaned_data.get('passenger_count')
        try:
            count = int(value)
        except (TypeError, ValueError):
            count = 1
        count = max(1, min(7, count))
        self.passenger_count = count
        return count

    def clean(self):
        cleaned_data = super().clean()
        today_value = date.today()
        available_count = len(self.available_seats)
        if self.passenger_count > available_count:
            raise forms.ValidationError(
                f'Only {available_count} seat(s) remaining. Please adjust passenger count or choose another flight.'
            )

        invalid_passengers: set[int] = set()
        for idx in range(self.passenger_count):
            prefix = f'passenger_{idx}'
            first_name = cleaned_data.get(f'{prefix}_first_name', '').strip()
            last_name = cleaned_data.get(f'{prefix}_last_name', '').strip()
            if not first_name:
                self.add_error(f'{prefix}_first_name', 'First name is required for each passenger.')
                invalid_passengers.add(idx)
            if not last_name:
                self.add_error(f'{prefix}_last_name', 'Last name is required for each passenger.')
                invalid_passengers.add(idx)

            dob_key = f'{prefix}_date_of_birth'
            dob_value = cleaned_data.get(dob_key)
            if dob_value is None:
                invalid_passengers.add(idx)
            elif dob_value > today_value:
                self.add_error(dob_key, 'Date of birth cannot be in the future.')
                invalid_passengers.add(idx)

        if invalid_passengers:
            raise forms.ValidationError('Please complete all passenger details.')
        return cleaned_data

    def get_passenger_details(self) -> list[dict[str, Any]]:
        details: list[dict[str, Any]] = []
        for idx in range(self.passenger_count):
            prefix = f'passenger_{idx}'
            dob_value = self.cleaned_data.get(f'{prefix}_date_of_birth')
            if hasattr(dob_value, 'isoformat'):
                dob_serialized: str | None = dob_value.isoformat()
            else:
                dob_serialized = dob_value if isinstance(dob_value, str) else None
            details.append({
                'first_name': self.cleaned_data.get(f'{prefix}_first_name', '').strip(),
                'last_name': self.cleaned_data.get(f'{prefix}_last_name', '').strip(),
                'contact_number': self.cleaned_data.get(f'{prefix}_contact_number', '').strip(),
                'date_of_birth': dob_serialized,
            })
        return details


class FlightPaymentForm(forms.Form):
    payment_token = forms.CharField(required=False, widget=forms.HiddenInput)

    BILLING_CONFIGURATION: list[dict[str, Any]] = [
        {
            'name': 'cardholder_first_name',
            'field': forms.CharField(max_length=120),
            'label': 'Cardholder first name',
            'placeholder': 'First name on card',
            'autocomplete': 'cc-given-name',
            'required': True,
            'full_width': False,
        },
        {
            'name': 'cardholder_last_name',
            'field': forms.CharField(max_length=120),
            'label': 'Cardholder last name',
            'placeholder': 'Last name on card',
            'autocomplete': 'cc-family-name',
            'required': True,
            'full_width': False,
        },
        {
            'name': 'cardholder_address_line1',
            'field': forms.CharField(max_length=160),
            'label': 'Billing address line 1',
            'placeholder': 'Street address',
            'autocomplete': 'cc-address-line1',
            'required': True,
            'full_width': True,
        },
        {
            'name': 'cardholder_address_line2',
            'field': forms.CharField(max_length=160, required=False),
            'label': 'Billing address line 2 (optional)',
            'placeholder': 'Apartment, suite, etc. (optional)',
            'autocomplete': 'cc-address-line2',
            'required': False,
            'full_width': True,
        },
        {
            'name': 'cardholder_address_city',
            'field': forms.CharField(max_length=80),
            'label': 'City',
            'placeholder': 'City',
            'autocomplete': 'cc-address-level2',
            'required': True,
            'full_width': False,
        },
        {
            'name': 'cardholder_address_state',
            'field': forms.CharField(max_length=80),
            'label': 'State / Province',
            'placeholder': 'State or region',
            'autocomplete': 'cc-address-level1',
            'required': True,
            'full_width': False,
        },
        {
            'name': 'cardholder_address_postal_code',
            'field': forms.CharField(max_length=20),
            'label': 'Postal / ZIP code',
            'placeholder': 'ZIP / postal code',
            'autocomplete': 'cc-postal-code',
            'required': True,
            'full_width': False,
        },
        {
            'name': 'cardholder_address_country',
            'field': forms.CharField(max_length=2, min_length=2),
            'label': 'Country',
            'placeholder': 'Country code (e.g. US)',
            'autocomplete': 'cc-country',
            'required': True,
            'full_width': False,
        },
    ]

    def __init__(self, *args, **kwargs):
        self.stripe_enabled = bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PUBLISHABLE_KEY)
        super().__init__(*args, **kwargs)

        self.billing_fields: list[dict[str, Any]] = []
        self._billing_required_fields: list[str] = []
        self._billing_labels: dict[str, str] = {}

        self.fields['payment_token'].required = self.stripe_enabled
        if self.stripe_enabled:
            self.fields['payment_token'].error_messages['required'] = (
                'Payment authorization is required before we can confirm your booking.'
            )

        billing_input_classes = 'w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-500'

        for definition in self.BILLING_CONFIGURATION:
            field_name: str = definition['name']
            field_obj: forms.Field = definition['field']
            label: str = definition['label']
            placeholder: str = definition['placeholder']
            autocomplete: str = definition['autocomplete']
            required: bool = definition['required']
            full_width: bool = definition['full_width']

            field_obj.label = label
            if required and self.stripe_enabled:
                self._billing_labels[field_name] = label
                field_obj.required = True
                field_obj.error_messages['required'] = f'{label} is required for card payments.'
                self._billing_required_fields.append(field_name)
            else:
                field_obj.required = False

            attrs = {
                'class': billing_input_classes,
                'placeholder': placeholder,
                'autocomplete': autocomplete,
            }
            if not isinstance(field_obj.widget.attrs, dict):
                field_obj.widget.attrs = {}
            field_obj.widget.attrs.update(attrs)

            self.fields[field_name] = field_obj
            field = self[field_name]
            self.billing_fields.append({
                'field': field,
                'label': label,
                'full_width': full_width,
                'optional': not required,
            })

    def clean(self):
        cleaned_data = super().clean()
        if self.stripe_enabled:
            token_value = (cleaned_data.get('payment_token') or '').strip()
            if not token_value:
                raise forms.ValidationError('Please complete payment authorization before confirming your booking.')

            for field_name in self._billing_required_fields:
                value = cleaned_data.get(field_name, '')
                if isinstance(value, str):
                    value = value.strip()
                    cleaned_data[field_name] = value
                if not value:
                    label = self._billing_labels.get(field_name, 'This field')
                    self.add_error(field_name, f'{label} is required for card payments.')

        return cleaned_data

    def clean_cardholder_address_country(self) -> str:
        value = self.cleaned_data.get('cardholder_address_country', '')
        if not value:
            return value
        value = value.strip().upper()
        if len(value) != 2:
            raise forms.ValidationError('Enter the 2-letter country code (e.g. US).')
        return value

    def get_billing_details(self) -> dict[str, Any]:
        return {
            'first_name': self.cleaned_data.get('cardholder_first_name', '').strip(),
            'last_name': self.cleaned_data.get('cardholder_last_name', '').strip(),
            'address_line1': self.cleaned_data.get('cardholder_address_line1', '').strip(),
            'address_line2': self.cleaned_data.get('cardholder_address_line2', '').strip(),
            'city': self.cleaned_data.get('cardholder_address_city', '').strip(),
            'state': self.cleaned_data.get('cardholder_address_state', '').strip(),
            'postal_code': self.cleaned_data.get('cardholder_address_postal_code', '').strip(),
            'country': self.cleaned_data.get('cardholder_address_country', '').strip(),
        }
