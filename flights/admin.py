from django.contrib import admin
from django.forms.models import BaseInlineFormSet

from .models import Flight, FlightBooking, FlightBookingSeat, FlightSeat


class BaseSeatFormSet(BaseInlineFormSet):
    leg: str = FlightSeat.Leg.OUTBOUND

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        return queryset.filter(leg=self.leg)

    def save_new(self, form, commit=True):  # type: ignore[override]
        obj = super().save_new(form, commit=False)
        obj.leg = self.leg
        if commit:
            obj.save()
            form.save_m2m()
        return obj


class BaseSeatInline(admin.TabularInline):
    model = FlightSeat
    extra = 0
    fields = ('seat_number', 'seat_class', 'price_modifier', 'is_reserved')
    exclude = ('leg',)
    ordering = ('seat_number',)
    show_change_link = False
    can_delete = True


class OutboundSeatFormSet(BaseSeatFormSet):
    leg = FlightSeat.Leg.OUTBOUND


class OutboundSeatInline(BaseSeatInline):
    verbose_name_plural = 'Seats'
    formset = OutboundSeatFormSet


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'origin',
        'destination',
        'departure_time',
        'available_seats',
        'is_active',
    )
    search_fields = ('code', 'origin', 'destination')
    list_filter = ('is_active', 'departure_time')
    fieldsets = (
        ('Flight details', {
            'fields': (
                'code',
                'origin',
                'destination',
                'departure_time',
                'arrival_time',
                'base_price',
                'description',
                'available_seats',
                'is_active',
            ),
        }),
    )
    inlines = [OutboundSeatInline]
    readonly_fields = ('available_seats',)


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
