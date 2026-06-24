from django.contrib import admin

from .models import BankDetail, BusinessCategory, Company, Director, PacraDetail


class DirectorInline(admin.TabularInline):
    model = Director
    extra = 0


class BankDetailInline(admin.TabularInline):
    model = BankDetail
    extra = 0


class PacraDetailInline(admin.StackedInline):
    model = PacraDetail
    extra = 0
    max_num = 1


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'tpin', 'registration_number', 'email')
    search_fields = ('name', 'tpin', 'registration_number')
    filter_horizontal = ('business_categories',)
    inlines = [DirectorInline, BankDetailInline, PacraDetailInline]


admin.site.register(BusinessCategory)

# Register your models here.
