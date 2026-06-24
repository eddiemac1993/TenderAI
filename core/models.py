from django.db import models

from quotations.models import TaxType


class SystemSettings(models.Model):
    default_tax_type = models.CharField(max_length=10, choices=TaxType.choices, default=TaxType.NONE)
    default_validity_period_days = models.PositiveIntegerField(default=30)
    default_prepared_by_name = models.CharField(max_length=120, blank=True)
    default_currency = models.CharField(max_length=20, default='ZMW')
    letterhead = models.FileField(upload_to='settings/letterheads/', blank=True)
    signature = models.FileField(upload_to='settings/signatures/', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'system settings'
        verbose_name_plural = 'system settings'

    def __str__(self):
        return 'TenderAI system settings'

    @classmethod
    def load(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

# Create your models here.
