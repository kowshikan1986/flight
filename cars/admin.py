from django.contrib import admin

from .models import Car, CarAvailability, CarBooking


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
	list_display = ('company', 'model', 'category', 'location', 'price_per_day', 'is_active')
	search_fields = ('company', 'model', 'location')
	list_filter = ('category', 'is_active', 'location')


@admin.register(CarAvailability)
class CarAvailabilityAdmin(admin.ModelAdmin):
	list_display = ('car', 'date', 'is_available')
	search_fields = ('car__company', 'car__model')
	list_filter = ('is_available', 'date')
	autocomplete_fields = ('car',)


@admin.register(CarBooking)
class CarBookingAdmin(admin.ModelAdmin):
	list_display = (
		'reference_number',
		'user',
		'car',
		'pickup_date',
		'dropoff_date',
		'status',
		'payment_status',
	)
	search_fields = ('reference_number', 'user__email', 'car__company', 'car__model')
	list_filter = ('status', 'payment_status', 'pickup_date', 'dropoff_date')
	readonly_fields = ('reference_number', 'created_at', 'updated_at')
	autocomplete_fields = ('user', 'car')
