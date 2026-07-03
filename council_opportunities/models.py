from django.db import models
from django.urls import reverse
from django.utils import timezone


class CouncilPage(models.Model):
    name = models.CharField(max_length=180)
    facebook_url = models.URLField(max_length=500, blank=True)
    district = models.CharField(max_length=120, blank=True)
    province = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['province', 'district', 'name']

    def __str__(self):
        return self.name


class CouncilPost(models.Model):
    class Category(models.TextChoices):
        CDF = 'CDF', 'CDF'
        TENDER = 'Tender', 'Tender'
        RFQ = 'RFQ', 'RFQ'
        PROCUREMENT = 'Procurement', 'Procurement'
        GRANT = 'Grant', 'Grant'
        BURSARY = 'Bursary', 'Bursary'
        OTHER = 'Other', 'Other'

    council_page = models.ForeignKey(CouncilPage, on_delete=models.CASCADE, related_name='posts')
    post_text = models.TextField()
    post_url = models.URLField(max_length=700, unique=True)
    date_posted = models.DateTimeField(null=True, blank=True)
    date_scraped = models.DateTimeField(default=timezone.now)
    matched_keywords = models.JSONField(default=list, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    detected_deadline = models.DateField(null=True, blank=True)
    attachment_url = models.URLField(max_length=700, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_posted', '-date_scraped', '-id']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['detected_deadline']),
            models.Index(fields=['date_posted']),
        ]

    def __str__(self):
        return f'{self.council_page}: {self.post_text[:80]}'

    def get_absolute_url(self):
        return reverse('council_opportunities:list')


class ScrapeRun(models.Model):
    class Status(models.TextChoices):
        STARTED = 'STARTED', 'Started'
        SUCCESS = 'SUCCESS', 'Success'
        PARTIAL = 'PARTIAL', 'Partial'
        FAILED = 'FAILED', 'Failed'

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.STARTED)
    pages_checked = models.PositiveIntegerField(default=0)
    posts_found = models.PositiveIntegerField(default=0)
    posts_created = models.PositiveIntegerField(default=0)
    posts_updated = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.get_status_display()} at {self.started_at:%Y-%m-%d %H:%M}'
