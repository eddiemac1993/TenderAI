from django.contrib import admin

from .models import CompanyDocument


@admin.register(CompanyDocument)
class CompanyDocumentAdmin(admin.ModelAdmin):
    list_display = ('company', 'document_type', 'title', 'issue_date', 'expiry_date', 'is_expired')
    list_filter = ('document_type', 'company')
    search_fields = ('title', 'company__name')

# Register your models here.
