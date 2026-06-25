from django import forms

from .models import CompanyDocument


class CompanyDocumentForm(forms.ModelForm):
    class Meta:
        model = CompanyDocument
        fields = ['company', 'document_type', 'title', 'file', 'issue_date', 'expiry_date', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={'autocomplete': 'off', 'placeholder': 'Leave blank to use the document type as the title'}),
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = False
        self.fields['title'].help_text = 'Optional. If blank, TenderAI will use the selected document type.'
        self.fields['notes'].required = False
        for field in self.fields.values():
            css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs.setdefault('class', css_class)

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if title:
            return title
        document_type = self.cleaned_data.get('document_type')
        if document_type:
            return CompanyDocument.DocumentType(document_type).label
        return 'Company Document'
