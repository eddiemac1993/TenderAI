from django.contrib import admin

from .models import BidTask, Tender, TenderMatch, TenderRequirement, ZppaScrapeLog


class TenderRequirementInline(admin.TabularInline):
    model = TenderRequirement
    extra = 0


class TenderMatchInline(admin.TabularInline):
    model = TenderMatch
    extra = 0
    readonly_fields = ('calculated_at',)


class BidTaskInline(admin.TabularInline):
    model = BidTask
    extra = 0


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = ('title', 'tender_number', 'zppa_resource_id', 'procuring_entity', 'source', 'closing_date', 'status')
    list_filter = ('source', 'status', 'category')
    search_fields = ('title', 'tender_number', 'zppa_resource_id', 'procuring_entity')
    readonly_fields = ('zppa_details',)
    inlines = [TenderRequirementInline, TenderMatchInline, BidTaskInline]


admin.site.register(TenderRequirement)
admin.site.register(TenderMatch)
admin.site.register(BidTask)


@admin.register(ZppaScrapeLog)
class ZppaScrapeLogAdmin(admin.ModelAdmin):
    list_display = ('started_at', 'finished_at', 'status', 'created_count', 'updated_count', 'today_only', 'limit')
    readonly_fields = ('started_at', 'finished_at')

# Register your models here.
