from django import forms

from .models import SolicitationDocument


class SolicitationDocumentForm(forms.ModelForm):
    class Meta:
        model = SolicitationDocument
        fields = ['file']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs.setdefault('class', 'form-control')
        self.fields['file'].widget.attrs.setdefault('accept', '.pdf,.docx,.xml,.txt')


class TenderChatForm(forms.Form):
    question = forms.CharField(
        label='Ask TenderAI',
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Ask about requirements, forms, deadlines, bid security, submission address, or disqualification risks...',
            }
        ),
    )
