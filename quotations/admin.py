from django.contrib import admin

from .models import Invoice, InvoiceItem, Quotation, QuotationItem


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('number', 'company', 'customer_name', 'date', 'tax_type')
    search_fields = ('number', 'customer_name', 'company__name')
    inlines = [QuotationItemInline]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'company', 'customer_name', 'date', 'due_date', 'tax_type')
    search_fields = ('number', 'customer_name', 'company__name')
    inlines = [InvoiceItemInline]

# Register your models here.
