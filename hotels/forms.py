"""Forms for hotel search and booking."""

from __future__ import annotations

from datetime import date

from django import forms

from .models import HotelRoomType, RoomType
from .services import check_availability


class HotelSearchForm(forms.Form):
    location = forms.CharField(max_length=120)
    check_in = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    check_out = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    room_type = forms.ChoiceField(choices=RoomType.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Where to?'
        })
        date_attrs = {
            'class': 'form-control form-control-lg',
        }
        self.fields['check_in'].widget.attrs.update(date_attrs | {'placeholder': 'Check-in'})
        self.fields['check_out'].widget.attrs.update(date_attrs | {'placeholder': 'Check-out'})
        self.fields['room_type'].widget.attrs.update({
            'class': 'form-select form-select-lg'
        })

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')
        if check_in and check_out and check_in >= check_out:
            raise forms.ValidationError('Check-out date must be after check-in date')
        if check_in and check_in < date.today():
            raise forms.ValidationError('Check-in date must be in the future')
        return cleaned_data


class HotelBookingForm(forms.Form):
    room_type_id = forms.IntegerField(widget=forms.HiddenInput)
    check_in = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    check_out = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    rooms = forms.IntegerField(min_value=1, initial=1)
    guests = forms.IntegerField(min_value=1, initial=1)
    surname = forms.CharField(max_length=120)
    contact_email = forms.EmailField()
    special_requests = forms.CharField(widget=forms.Textarea, required=False)
    payment_token = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['check_in', 'check_out']:
            self.fields[field_name].widget.attrs.update({'class': 'form-control', 'placeholder': field_name.replace('_', ' ').title()})
        self.fields['rooms'].widget.attrs.update({'class': 'form-control'} )
        self.fields['guests'].widget.attrs.update({'class': 'form-control'} )
        self.fields['surname'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Surname'})
        self.fields['contact_email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Email'})
        self.fields['special_requests'].widget.attrs.update({'class': 'form-control', 'rows': 3})

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')
        room_type_id = cleaned_data.get('room_type_id')
        rooms = cleaned_data.get('rooms') or 1
        if check_in and check_out and check_in >= check_out:
            raise forms.ValidationError('Check-out date must be after check-in date')
        if check_in and check_in < date.today():
            raise forms.ValidationError('Check-in date must be in the future')
        if room_type_id and check_in and check_out:
            try:
                room_type = HotelRoomType.objects.select_related('hotel').get(id=room_type_id)
            except HotelRoomType.DoesNotExist:
                raise forms.ValidationError('Selected room type is no longer available')
            availability = check_availability(room_type, check_in, check_out, rooms)
            if not availability.available:
                raise forms.ValidationError(availability.reasons)
            cleaned_data['room_type'] = room_type
        return cleaned_data
