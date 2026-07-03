from django import forms

from .models import BidPack


class BidPackForm(forms.ModelForm):
    class Meta:
        model = BidPack
        fields = ['tender', 'company', 'include_cover_letter', 'include_checklist', 'include_company_profile', 'include_price_schedule']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            from core.tenancy import user_organization

            organization = user_organization(user)
            self.fields['company'].queryset = self.fields['company'].queryset.filter(organization=organization)
        for name, field in self.fields.items():
            if not name.startswith('include_'):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-check-input')
