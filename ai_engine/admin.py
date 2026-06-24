from django.contrib import admin

from .models import SolicitationDocument, TenderAnalysisRun


@admin.register(SolicitationDocument)
class SolicitationDocumentAdmin(admin.ModelAdmin):
    list_display = ('tender', 'file', 'uploaded_at')
    readonly_fields = ('extracted_text', 'analysis_summary', 'uploaded_at')


@admin.register(TenderAnalysisRun)
class TenderAnalysisRunAdmin(admin.ModelAdmin):
    list_display = ('tender', 'status', 'created_at')
    readonly_fields = ('created_at',)

# Register your models here.
