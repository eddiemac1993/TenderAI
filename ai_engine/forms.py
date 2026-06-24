from django import forms

from .models import SolicitationDocument


class SolicitationDocumentForm(forms.ModelForm):
    class Meta:
        model = SolicitationDocument
        fields = ['file']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs.setdefault('class', 'form-control')
