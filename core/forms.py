from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import Organization, SupportChatMessage, SupportChatSession, SystemSettings, UserProfile


class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = [
            'default_tax_type',
            'default_validity_period_days',
            'default_prepared_by_name',
            'default_currency',
            'letterhead',
            'signature',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class SupportChatStartForm(forms.Form):
    user_name = forms.CharField(label='Your name', max_length=120, required=False)
    user_email = forms.EmailField(label='Email', required=False)
    question = forms.CharField(
        label='What do you need help with?',
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Example: How do I generate bid documents from a ZPPA tender URL?'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class SupportChatQuestionForm(forms.Form):
    question = forms.CharField(
        label='Ask another question',
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Type your question here...'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['question'].widget.attrs.setdefault('class', 'form-control')


class SupportChatAdminReplyForm(forms.Form):
    message = forms.CharField(label='Admin clarification', widget=forms.Textarea(attrs={'rows': 3}))
    status = forms.ChoiceField(choices=SupportChatSession.Status.choices, initial=SupportChatSession.Status.NEEDS_ADMIN)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['message'].widget.attrs.setdefault('class', 'form-control')
        self.fields['status'].widget.attrs.setdefault('class', 'form-select')


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'province', 'district', 'contact_email', 'contact_phone', 'active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'form-check-input' if name == 'active' else 'form-control')


class TeamUserCreateForm(UserCreationForm):
    organization = forms.ModelChoiceField(queryset=Organization.objects.none(), required=False)
    role = forms.ChoiceField(choices=UserProfile.Role.choices, initial=UserProfile.Role.STAFF)
    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'organization', 'role']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.is_superuser:
            self.fields['organization'].queryset = Organization.objects.order_by('name')
            self.fields['organization'].required = True
        else:
            from .tenancy import user_organization

            organization = user_organization(user)
            self.fields['organization'].queryset = Organization.objects.filter(pk=organization.pk) if organization else Organization.objects.none()
            self.fields['organization'].initial = organization
            self.fields['organization'].widget = forms.HiddenInput()
        for field in self.fields.values():
            css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs.setdefault('class', css_class)
