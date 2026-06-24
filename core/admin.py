from django.contrib import admin

from .models import SystemSettings


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('default_tax_type', 'default_validity_period_days', 'default_prepared_by_name', 'default_currency', 'updated_at')

# Register your models here.
