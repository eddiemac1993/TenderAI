from django.db import models
from django.urls import reverse
from django.utils import timezone

from companies.models import BusinessCategory, Company


class Tender(models.Model):
    class Source(models.TextChoices):
        ZPPA = 'ZPPA', 'ZPPA'
        MANUAL = 'MANUAL', 'Manual'

    class Status(models.TextChoices):
        NEW = 'NEW', 'New'
        REVIEWING = 'REVIEWING', 'Reviewing'
        INTERESTED = 'INTERESTED', 'Interested'
        NOT_INTERESTED = 'NOT_INTERESTED', 'Not Interested'
        PREPARING_BID = 'PREPARING_BID', 'Preparing Bid'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        LOST = 'LOST', 'Lost'
        WON = 'WON', 'Won'

    title = models.CharField(max_length=240)
    tender_number = models.CharField(max_length=120, blank=True)
    zppa_resource_id = models.CharField(max_length=40, blank=True)
    procuring_entity = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    category = models.ForeignKey(BusinessCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='tenders')
    closing_date = models.DateField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    closing_at = models.DateTimeField(null=True, blank=True)
    submission_method = models.CharField(max_length=180, blank=True)
    procurement_method = models.CharField(max_length=180, blank=True)
    zppa_details = models.JSONField(default=list, blank=True)
    bid_security_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    participation_fee = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    site_visit_date = models.DateField(null=True, blank=True)
    tender_document = models.FileField(upload_to='tender_documents/%Y/%m/', blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NEW)
    notes = models.TextField(blank=True)
    imported_reference = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['closing_date', 'title']

    def __str__(self):
        return self.title

    @property
    def is_closed(self):
        return bool(self.closing_date and self.closing_date < timezone.localdate())

    def get_absolute_url(self):
        return reverse('tenders:detail', args=[self.pk])


class TenderRequirement(models.Model):
    class RequirementType(models.TextChoices):
        ELIGIBILITY = 'ELIGIBILITY', 'Eligibility'
        MANDATORY_DOCUMENT = 'MANDATORY_DOCUMENT', 'Mandatory Document'
        BID_SECURITY = 'BID_SECURITY', 'Bid Security'
        SITE_VISIT = 'SITE_VISIT', 'Site Visit'
        EVALUATION = 'EVALUATION', 'Evaluation Criteria'
        REQUIRED_FORM = 'REQUIRED_FORM', 'Required Form'
        EXPERIENCE = 'EXPERIENCE', 'Similar Experience'
        CERTIFICATE = 'CERTIFICATE', 'Required Certificate'
        OTHER = 'OTHER', 'Other'

    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='requirements')
    requirement_type = models.CharField(max_length=40, choices=RequirementType.choices)
    description = models.TextField()
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        ordering = ['tender', 'requirement_type']

    def __str__(self):
        return f'{self.tender} - {self.get_requirement_type_display()}'


class TenderMatch(models.Model):
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='matches')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tender_matches')
    score = models.PositiveSmallIntegerField(default=0)
    missing_documents = models.TextField(blank=True)
    expired_documents = models.TextField(blank=True)
    recommended_action = models.TextField(blank=True)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tender', 'company')
        ordering = ['-score', 'company__name']

    def __str__(self):
        return f'{self.company} match for {self.tender}: {self.score}%'


class ZppaScrapeLog(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, default='STARTED')
    today_only = models.BooleanField(default=True)
    limit = models.PositiveIntegerField(default=10)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'ZPPA scrape {self.status} at {self.started_at:%Y-%m-%d %H:%M}'
