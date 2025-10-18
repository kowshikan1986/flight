from django.contrib import admin

from .models import Hotel, HotelBooking, HotelRoomInventory, HotelRoomType


class HotelRoomTypeInline(admin.TabularInline):
	model = HotelRoomType
	extra = 0


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
	list_display = ('name', 'location', 'contact_email', 'is_active')
	search_fields = ('name', 'location', 'contact_email')
	list_filter = ('is_active',)
	prepopulated_fields = {'slug': ('name',)}
	inlines = [HotelRoomTypeInline]


@admin.register(HotelRoomType)
class HotelRoomTypeAdmin(admin.ModelAdmin):
	list_display = ('hotel', 'room_type', 'base_price', 'total_rooms')
	search_fields = ('hotel__name',)
	list_filter = ('room_type',)


@admin.register(HotelRoomInventory)
class HotelRoomInventoryAdmin(admin.ModelAdmin):
	list_display = ('room_type', 'date', 'available_rooms')
	search_fields = ('room_type__hotel__name',)
	list_filter = ('date',)
	autocomplete_fields = ('room_type',)


@admin.register(HotelBooking)
class HotelBookingAdmin(admin.ModelAdmin):
	list_display = (
		'reference_number',
		'user',
		'room_type',
		'check_in',
		'check_out',
		'status',
		'payment_status',
	)
	search_fields = ('reference_number', 'user__email', 'room_type__hotel__name')
	list_filter = ('status', 'payment_status', 'check_in', 'check_out')
	readonly_fields = ('reference_number', 'created_at', 'updated_at')
	autocomplete_fields = ('user', 'room_type')
