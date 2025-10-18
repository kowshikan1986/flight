from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
	fieldsets = (
		("Branding", {"fields": ("logo", "custom_header", "hero_image")}),
		("Promotions", {"fields": ("advertisement",)}),
	)

	def has_add_permission(self, request):
		return not SiteSettings.objects.exists()

	def has_delete_permission(self, request, obj=None):
		return False

	def changelist_view(self, request, extra_context=None):
		settings_obj, _ = SiteSettings.objects.get_or_create(pk=1)
		url = reverse('admin:core_sitesettings_change', args=[settings_obj.pk])
		return HttpResponseRedirect(url)
