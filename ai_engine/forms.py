from django import forms

from .models import SolicitationDocument


class SolicitationDocumentForm(forms.ModelForm):
    class Meta:
        model = SolicitationDocument
        fields = ['file']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs.setdefault('class', 'form-control')


class TenderChatForm(forms.Form):
    question = forms.CharField(
        label='Ask TenderAI',
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Example: What documents are required, and what should I do next?',
            }
        ),
    )
