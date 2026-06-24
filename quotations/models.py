from decimal import Decimal

from django.db import models
from django.urls import reverse

from companies.models import Company


class TaxType(models.TextChoices):
    NONE = 'NONE', 'None'
    TOT = 'TOT', 'TOT 4%'
    VAT = 'VAT', 'VAT 16%'


TAX_RATES = {
    TaxType.NONE: Decimal('0.00'),
    TaxType.TOT: Decimal('0.04'),
    TaxType.VAT: Decimal('0.16'),
}


class CommercialDocument(models.Model):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='%(class)ss')
    customer_name = models.CharField(max_length=180)
    customer_tpin = models.CharField('Customer TPIN', max_length=50, blank=True)
    customer_address = models.TextField(blank=True)
    number = models.CharField(max_length=80, unique=True)
    date = models.DateField()
    tax_type = models.CharField(max_length=10, choices=TaxType.choices, default=TaxType.NONE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-date', '-id']

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), Decimal('0.00'))

    @property
    def tax_amount(self):
        return (self.subtotal * TAX_RATES[self.tax_type]).quantize(Decimal('0.01'))

    @property
    def total(self):
        return self.subtotal + self.tax_amount


class Quotation(CommercialDocument):
    validity_period_days = models.PositiveIntegerField(default=30)

    def __str__(self):
        return f'Quotation {self.number}'

    def get_absolute_url(self):
        return reverse('quotations:quotation_detail', args=[self.pk])


class Invoice(CommercialDocument):
    due_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f'Invoice {self.number}'

    def get_absolute_url(self):
        return reverse('quotations:invoice_detail', args=[self.pk])


class LineItem(models.Model):
    description = models.CharField(max_length=240)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        abstract = True

    @property
    def line_total(self):
        return (self.quantity * self.unit_price).quantize(Decimal('0.01'))

    def __str__(self):
        return self.description


class QuotationItem(LineItem):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')


class InvoiceItem(LineItem):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')

# Create your models here.
