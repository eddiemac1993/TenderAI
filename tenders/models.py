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
    clarification_address = models.TextField(blank=True)
    submission_address = models.TextField(blank=True)
    itb_11_items = models.JSONField(default=list, blank=True)
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
        deadline = self.deadline_date
        return bool(deadline and deadline < timezone.localdate())

    @property
    def deadline_date(self):
        if self.closing_at:
            return self.closing_at.date()
        return self.closing_date

    @property
    def days_until_deadline(self):
        deadline = self.deadline_date
        if not deadline:
            return None
        return (deadline - timezone.localdate()).days

    @property
    def urgency_label(self):
        days = self.days_until_deadline
        if days is None:
            return 'No deadline'
        if days < 0:
            return 'Closed'
        if days == 0:
            return 'Closing today'
        if days <= 3:
            return f'{days} day(s) left'
        if days <= 7:
            return 'Closing this week'
        return 'Open'

    @property
    def days_left_label(self):
        days = self.days_until_deadline
        if days is None:
            return 'No deadline'
        if days < 0:
            count = abs(days)
            return f'Closed {count} day{"s" if count != 1 else ""} ago'
        if days == 0:
            return 'Closing today'
        return f'{days} day{"s" if days != 1 else ""} left'

    @property
    def lot_count(self):
        lots = {
            str(item.get('lot_title') or item.get('lot') or '').strip()
            for item in self.itb_11_items or []
            if str(item.get('lot_title') or item.get('lot') or '').strip()
        }
        return len(lots)

    @property
    def urgency_class(self):
        days = self.days_until_deadline
        if days is None:
            return 'secondary'
        if days < 0:
            return 'dark'
        if days <= 3:
            return 'danger'
        if days <= 7:
            return 'warning'
        return 'success'

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


class BidTask(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        DONE = 'DONE', 'Done'
        BLOCKED = 'BLOCKED', 'Blocked'

    class Priority(models.TextChoices):
        HIGH = 'HIGH', 'High'
        MEDIUM = 'MEDIUM', 'Medium'
        LOW = 'LOW', 'Low'

    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='bid_tasks')
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'status', 'due_date', 'title']
        unique_together = ('tender', 'title')

    def __str__(self):
        return f'{self.tender} - {self.title}'

    @property
    def is_done(self):
        return self.status == self.Status.DONE

    @property
    def is_blocked(self):
        return self.status == self.Status.BLOCKED

    @property
    def status_class(self):
        if self.status == self.Status.DONE:
            return 'success'
        if self.status == self.Status.BLOCKED:
            return 'danger'
        return 'warning'

    @property
    def priority_class(self):
        if self.priority == self.Priority.HIGH:
            return 'danger'
        if self.priority == self.Priority.LOW:
            return 'secondary'
        return 'warning'


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
