from django import forms

from .models import BidPack


class BidPackForm(forms.ModelForm):
    class Meta:
        model = BidPack
        fields = ['tender', 'company', 'quotation', 'include_cover_letter', 'include_checklist', 'include_company_profile', 'include_price_schedule']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not name.startswith('include_'):
                field.widget.attrs.setdefault('class', 'form-control')
