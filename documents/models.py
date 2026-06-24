from django.db import models
from django.urls import reverse
from django.utils import timezone

from companies.models import Company


class CompanyDocument(models.Model):
    class DocumentType(models.TextChoices):
        PACRA = 'PACRA', 'PACRA'
        ZRA_TAX_CLEARANCE = 'ZRA_TAX_CLEARANCE', 'ZRA Tax Clearance'
        TPIN_CERTIFICATE = 'TPIN_CERTIFICATE', 'TPIN Certificate'
        NAPSA = 'NAPSA', 'NAPSA'
        WORKERS_COMPENSATION = 'WORKERS_COMPENSATION', 'Workers Compensation'
        NCC = 'NCC', 'NCC'
        ZPPA_REGISTRATION = 'ZPPA_REGISTRATION', 'ZPPA Registration'
        BANK_CONFIRMATION = 'BANK_CONFIRMATION', 'Bank Confirmation Letter'
        PAST_CONTRACT = 'PAST_CONTRACT', 'Past Contract'
        COMPANY_PROFILE = 'COMPANY_PROFILE', 'Company Profile'
        OTHER = 'OTHER', 'Other'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=40, choices=DocumentType.choices)
    title = models.CharField(max_length=180)
    file = models.FileField(upload_to='company_documents/%Y/%m/')
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['company__name', 'document_type', '-expiry_date']

    def __str__(self):
        company_name = self.company.name if self.company_id else 'Unassigned company'
        return f'{company_name} - {self.get_document_type_display()}'

    @property
    def is_expired(self):
        return bool(self.expiry_date and self.expiry_date < timezone.localdate())

    def get_absolute_url(self):
        return reverse('documents:detail', args=[self.pk])

# Create your models here.
