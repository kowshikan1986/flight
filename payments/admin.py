from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = (
		'provider_reference',
		'user',
		'amount',
		'currency',
		'status',
		'provider',
		'created_at',
	)
	search_fields = ('provider_reference', 'user__email')
	list_filter = ('status', 'provider', 'currency', 'created_at')
	readonly_fields = ('created_at', 'updated_at')
	raw_id_fields = ('user',)
