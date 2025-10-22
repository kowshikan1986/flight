from django import forms
from django.contrib import admin

from .constants import VAN_HIRE_LOCATIONS
from .models import Car, CarAvailability, CarBooking
from .services import check_availability



class CarBookingAdminForm(forms.ModelForm):
	pickup_location = forms.ChoiceField(choices=VAN_HIRE_LOCATIONS)
	dropoff_location = forms.ChoiceField(choices=VAN_HIRE_LOCATIONS)

	class Meta:
		model = CarBooking
		fields = '__all__'

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		location_choices = list(VAN_HIRE_LOCATIONS)
		self.fields['pickup_location'].choices = [('', 'Select pick-up location')] + location_choices
		self.fields['dropoff_location'].choices = [('', 'Select drop-off location')] + location_choices
		self.fields['pickup_location'].widget.attrs.update({'class': 'vLargeTextField'})
		self.fields['dropoff_location'].widget.attrs.update({'class': 'vLargeTextField'})
		self.fields['contact_email'].widget.attrs.update({'class': 'vTextField'})

		car_id = self._resolve_car_id()
		if car_id:
			available_dates = list(
				CarAvailability.objects.filter(car_id=car_id, is_available=True).order_by('date').values_list('date', flat=True)
			)
			if self.instance and self.instance.pk and self.instance.pickup_date:
				if self.instance.pickup_date not in available_dates:
					available_dates.append(self.instance.pickup_date)
					available_dates.sort()
			if available_dates:
				dates_display = ', '.join(date.strftime('%b %d, %Y') for date in available_dates[:10])
				if len(available_dates) > 10:
					dates_display += ', …'
				self.fields['pickup_date'].help_text = f"Available dates: {dates_display}"
			else:
				self.fields['pickup_date'].help_text = 'No available dates recorded for this vehicle.'
		else:
			self.fields['pickup_date'].help_text = 'Select a car to view available pick-up dates.'

	def _resolve_car_id(self) -> int | None:
		if self.data.get(self.add_prefix('car')):
			try:
				return int(self.data[self.add_prefix('car')])
			except (TypeError, ValueError):
				return None
		if self.initial.get('car'):
			return self.initial['car'].id if isinstance(self.initial['car'], Car) else self.initial['car']
		if getattr(self.instance, 'car_id', None):
			return self.instance.car_id
		return None

	def clean(self):
		cleaned_data = super().clean()
		car = cleaned_data.get('car')
		pickup_date = cleaned_data.get('pickup_date')
		dropoff_date = cleaned_data.get('dropoff_date')
		if car and pickup_date and dropoff_date:
			availability = check_availability(car, pickup_date, dropoff_date)
			if not availability.available:
				raise forms.ValidationError(availability.reasons)
		return cleaned_data


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
	list_display = (
		'company',
		'model',
		'category',
		'pickup_location',
		'dropoff_location',
		'price_per_trip',
		'is_active',
	)
	search_fields = (
		'company',
		'model',
		'pickup_location',
		'dropoff_location',
		'location',
	)
	list_filter = (
		'category',
		'is_active',
		'pickup_location',
		'dropoff_location',
	)
	fieldsets = (
		('Car details', {
			'fields': ('company', 'model', 'category', 'seats', 'luggage_capacity', 'image', 'is_active'),
		}),
		('Route & pricing', {
			'fields': (
				'pickup_location',
				'dropoff_location',
				'default_pickup_date',
				'price_per_trip',
				'location',
			),
		}),
	)


@admin.register(CarAvailability)
class CarAvailabilityAdmin(admin.ModelAdmin):
	list_display = ('car', 'date', 'is_available')
	search_fields = ('car__company', 'car__model')
	list_filter = ('is_available', 'date')
	autocomplete_fields = ('car',)


@admin.register(CarBooking)
class CarBookingAdmin(admin.ModelAdmin):
	form = CarBookingAdminForm
	list_display = (
		'reference_number',
		'user',
		'car',
		'first_name',
		'last_name',
		'pickup_date',
		'dropoff_date',
		'status',
		'payment_status',
		'created_at',
	)
	list_filter = (
		'car__category',
		'status',
		'payment_status',
		'pickup_date',
		'dropoff_date',
	)
	search_fields = (
		'reference_number',
		'user__email',
		'car__company',
		'car__model',
		'pickup_location',
		'dropoff_location',
		'pickup_address',
		'first_name',
		'last_name',
		'contact_number',
	)
	readonly_fields = (
		'reference_number',
		'total_price',
		'created_at',
		'updated_at',
	)
	autocomplete_fields = ('user', 'car')
	list_select_related = ('user', 'car')
	ordering = ('-created_at',)
	fieldsets = (
		('Booking details', {
			'fields': (
				'reference_number',
				'user',
				'car',
				'pickup_location',
				'dropoff_location',
				'pickup_date',
				'dropoff_date',
				'pickup_time',
				'pickup_address',
				'contact_email',
				'first_name',
				'last_name',
				'contact_number',
				'total_price',
				'status',
				'payment_status',
				'payment_reference',
				'created_at',
				'updated_at',
			),
		}),
	)
