from django.db import models
from django.urls import reverse


class BusinessCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'business categories'

    def __str__(self):
        return self.name


class Company(models.Model):
    organization = models.ForeignKey('core.Organization', on_delete=models.PROTECT, related_name='companies', null=True, blank=True)
    name = models.CharField(max_length=180)
    tpin = models.CharField('TPIN', max_length=50, blank=True)
    registration_number = models.CharField(max_length=80, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    profile_summary = models.TextField(blank=True)
    letterhead_pdf = models.FileField(upload_to='company_letterheads/%Y/%m/', blank=True)
    business_categories = models.ManyToManyField(BusinessCategory, blank=True, related_name='companies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'companies'
        constraints = [
            models.UniqueConstraint(fields=['organization', 'name'], name='unique_company_name_per_organization'),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('companies:detail', args=[self.pk])


class Director(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='directors')
    name = models.CharField(max_length=160)
    national_id = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=60, blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        ordering = ['company__name', 'name']

    def __str__(self):
        return f'{self.name} - {self.company}'


class BankDetail(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='bank_details')
    bank_name = models.CharField(max_length=160)
    branch = models.CharField(max_length=120, blank=True)
    account_name = models.CharField(max_length=160)
    account_number = models.CharField(max_length=80)
    swift_code = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ['company__name', 'bank_name']

    def __str__(self):
        return f'{self.bank_name} - {self.account_number}'


class PacraDetail(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='pacra_detail')
    incorporation_number = models.CharField(max_length=80, blank=True)
    incorporation_date = models.DateField(null=True, blank=True)
    registration_status = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f'PACRA - {self.company}'

# Create your models here.
