from django import forms

from .models import BidTask, Tender, TenderRequirement


class TenderForm(forms.ModelForm):
    class Meta:
        model = Tender
        fields = [
            'title', 'tender_number', 'zppa_resource_id', 'procuring_entity', 'description',
            'source', 'category', 'closing_date', 'published_at', 'closing_at',
            'submission_method', 'procurement_method', 'bid_security_amount', 'participation_fee', 'site_visit_date',
            'tender_document', 'status', 'notes', 'imported_reference',
        ]
        widgets = {
            'closing_date': forms.DateInput(attrs={'type': 'date'}),
            'published_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'closing_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'site_visit_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class TenderRequirementForm(forms.ModelForm):
    class Meta:
        model = TenderRequirement
        fields = ['tender', 'requirement_type', 'description', 'is_mandatory']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'is_mandatory':
                field.widget.attrs.setdefault('class', 'form-control')


class BidTaskForm(forms.ModelForm):
    class Meta:
        model = BidTask
        fields = ['title', 'description', 'status', 'priority', 'due_date', 'notes']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs.setdefault('class', css_class)


class ZppaManualImportForm(forms.Form):
    title = forms.CharField(max_length=240)
    tender_number = forms.CharField(max_length=120, required=False)
    procuring_entity = forms.CharField(max_length=180)
    category_name = forms.CharField(max_length=120, required=False)
    closing_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    submission_method = forms.CharField(max_length=180, required=False)
    source_url_or_reference = forms.CharField(max_length=200, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class ZppaJsonImportForm(forms.Form):
    file = forms.FileField(help_text='Upload a JSON file exported by export_zppa_public_tenders.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs.setdefault('class', 'form-control')


class ZppaUrlImportForm(forms.Form):
    url = forms.URLField(
        label='ZPPA tender URL',
        help_text='Paste a public ZPPA tender page URL containing resourceId.',
        widget=forms.URLInput(attrs={'placeholder': 'https://eprocure.zppa.org.zm/epps/cft/prepareViewCfTWS.do?resourceId=...'}),
    )
    fetch_documents = forms.BooleanField(
        label='Fetch public solicitation/XML documents after import',
        required=False,
        initial=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['url'].widget.attrs.setdefault('class', 'form-control')
        self.fields['fetch_documents'].widget.attrs.setdefault('class', 'form-check-input')
