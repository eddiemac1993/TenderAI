from django import forms

from .models import Invoice, InvoiceItem, Quotation, QuotationItem


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class QuotationForm(BootstrapModelForm):
    class Meta:
        model = Quotation
        fields = ['company', 'customer_name', 'customer_tpin', 'customer_address', 'number', 'date', 'validity_period_days', 'tax_type', 'notes']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'}), 'customer_address': forms.Textarea(attrs={'rows': 3}), 'notes': forms.Textarea(attrs={'rows': 3})}


class InvoiceForm(BootstrapModelForm):
    class Meta:
        model = Invoice
        fields = ['company', 'customer_name', 'customer_tpin', 'customer_address', 'number', 'date', 'due_date', 'tax_type', 'notes']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'}), 'due_date': forms.DateInput(attrs={'type': 'date'}), 'customer_address': forms.Textarea(attrs={'rows': 3}), 'notes': forms.Textarea(attrs={'rows': 3})}


class QuotationItemForm(BootstrapModelForm):
    class Meta:
        model = QuotationItem
        fields = ['quotation', 'description', 'quantity', 'unit_price']


class InvoiceItemForm(BootstrapModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['invoice', 'description', 'quantity', 'unit_price']
