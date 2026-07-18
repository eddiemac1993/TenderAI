from django import forms

from .models import BankDetail, Company, Director, PacraDetail


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if widget.__class__.__name__ in {'CheckboxInput', 'CheckboxSelectMultiple'}:
                continue
            widget.attrs.setdefault('class', 'form-control')


class CompanyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Company
        fields = ['organization', 'name', 'tpin', 'registration_number', 'address', 'phone', 'email', 'website', 'profile_summary', 'letterhead_pdf', 'business_categories']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'profile_summary': forms.Textarea(attrs={'rows': 4}),
            'business_categories': forms.CheckboxSelectMultiple,
        }
        help_texts = {
            'letterhead_pdf': 'Upload a one-page PDF letterhead. TenderAI will place generated bid document text over it.',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not user or not user.is_superuser:
            self.fields.pop('organization', None)


class DirectorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Director
        fields = ['company', 'name', 'national_id', 'role', 'phone', 'email']


class BankDetailForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BankDetail
        fields = ['company', 'bank_name', 'branch', 'account_name', 'account_number', 'swift_code']


class PacraDetailForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PacraDetail
        fields = ['company', 'incorporation_number', 'incorporation_date', 'registration_status']
        widgets = {'incorporation_date': forms.DateInput(attrs={'type': 'date'})}
