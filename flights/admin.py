from django.contrib import admin

from .models import Flight, FlightBooking, FlightBookingSeat, FlightSeat


class FlightSeatInline(admin.TabularInline):
	model = FlightSeat
	extra = 0


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
	list_display = ('code', 'origin', 'destination', 'departure_time', 'arrival_time', 'is_active')
	search_fields = ('code', 'origin', 'destination')
	list_filter = ('is_active', 'departure_time')
	inlines = [FlightSeatInline]


class FlightBookingSeatInline(admin.TabularInline):
	model = FlightBookingSeat
	extra = 0
	autocomplete_fields = ('seat',)


@admin.register(FlightBooking)
class FlightBookingAdmin(admin.ModelAdmin):
	list_display = (
		'reference_number',
		'user',
		'flight',
		'passengers',
		'status',
		'payment_status',
		'created_at',
	)
	search_fields = ('reference_number', 'user__email', 'flight__code')
	list_filter = ('status', 'payment_status', 'flight__departure_time')
	readonly_fields = ('reference_number', 'created_at', 'updated_at')
	inlines = [FlightBookingSeatInline]
	autocomplete_fields = ('user', 'flight')


@admin.register(FlightSeat)
class FlightSeatAdmin(admin.ModelAdmin):
	list_display = ('flight', 'seat_number', 'seat_class', 'is_reserved')
	search_fields = ('flight__code', 'seat_number')
	list_filter = ('seat_class', 'is_reserved')
