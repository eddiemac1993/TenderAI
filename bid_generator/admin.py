from django.contrib import admin

from .models import BidPack


@admin.register(BidPack)
class BidPackAdmin(admin.ModelAdmin):
    list_display = ('tender', 'company', 'quotation', 'created_at')
    readonly_fields = ('created_at',)

# Register your models here.
