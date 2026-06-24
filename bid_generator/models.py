from django.db import models

from companies.models import Company
from quotations.models import Quotation
from tenders.models import Tender


class BidPack(models.Model):
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='bid_packs')
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='bid_packs')
    quotation = models.ForeignKey(Quotation, on_delete=models.SET_NULL, null=True, blank=True, related_name='bid_packs')
    include_cover_letter = models.BooleanField(default=True)
    include_checklist = models.BooleanField(default=True)
    include_company_profile = models.BooleanField(default=True)
    include_price_schedule = models.BooleanField(default=True)
    generated_docx = models.FileField(upload_to='bid_packs/docx/%Y/%m/', blank=True)
    generated_pdf = models.FileField(upload_to='bid_packs/pdf/%Y/%m/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Bid pack: {self.company} - {self.tender}'

# Create your models here.
