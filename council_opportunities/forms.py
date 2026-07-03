from django import forms

from .models import CouncilPage


class CouncilPageForm(forms.ModelForm):
    class Meta:
        model = CouncilPage
        fields = ['name', 'facebook_url', 'district', 'province', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Example: Lusaka City Council'}),
            'facebook_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.facebook.com/...'}),
            'district': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'District'}),
            'province': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Province'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CouncilPostImportForm(forms.Form):
    council_page = forms.ModelChoiceField(
        queryset=CouncilPage.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    post_url = forms.URLField(
        max_length=700,
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Paste public Facebook post, reel, or video URL'}),
    )
    post_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'placeholder': 'Optional: paste the Facebook caption/text here if Facebook hides it from the importer.',
                'rows': 5,
            }
        ),
    )
