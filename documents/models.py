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
        NCC_B = 'NCC_B', 'NCC B'
        NCC_R = 'NCC_R', 'NCC R'
        NCC_E = 'NCC_E', 'NCC E'
        ERB = 'ERB', 'ERB Registration / Licence'
        EIZ_CERTIFICATE = 'EIZ_CERTIFICATE', 'EIZ Certificate'
        ZEMA_LICENSE = 'ZEMA_LICENSE', 'ZEMA / Environmental Compliance'
        ROADWORTHINESS = 'ROADWORTHINESS', 'Roadworthiness / Vehicle Compliance'
        ZPPA_REGISTRATION = 'ZPPA_REGISTRATION', 'ZPPA Registration'
        BANK_CONFIRMATION = 'BANK_CONFIRMATION', 'Bank Confirmation Letter'
        AUDITED_FINANCIALS = 'AUDITED_FINANCIALS', 'Audited Financial Statements'
        DELIVERY_EVIDENCE = 'DELIVERY_EVIDENCE', 'Delivery Notes / LPO / GRN / Award Letters'
        TRAINING_PROGRAMME = 'TRAINING_PROGRAMME', 'Training Programme Evidence'
        WARRANTY_UNDERTAKING = 'WARRANTY_UNDERTAKING', 'Warranty / Undertaking Letter'
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

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.localdate()).days

    @property
    def is_expiring_soon(self):
        days = self.days_until_expiry
        return days is not None and 0 <= days <= 30

    @property
    def status_label(self):
        days = self.days_until_expiry
        if days is None:
            return 'No expiry'
        if days < 0:
            return 'Expired'
        if days == 0:
            return 'Expires today'
        if days <= 30:
            return f'Expires in {days} day(s)'
        return 'Ready'

    @property
    def status_class(self):
        days = self.days_until_expiry
        if days is None:
            return 'secondary'
        if days < 0:
            return 'danger'
        if days <= 30:
            return 'warning'
        return 'success'

    def get_absolute_url(self):
        return reverse('documents:detail', args=[self.pk])

# Create your models here.
