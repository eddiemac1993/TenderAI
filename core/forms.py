from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

from .models import MessagePost, MessageThread, Organization, SupportChatMessage, SupportChatSession, SystemSettings, UserProfile


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


class PublicRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    organization_name = forms.CharField(label='Company / organization name', max_length=180)
    phone = forms.CharField(required=False, max_length=60)
    accept_terms = forms.BooleanField(
        required=True,
        label='I accept the TenderAI terms and understand that all generated tender documents must be reviewed before submission.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'email', 'organization_name', 'phone', 'password1', 'password2', 'accept_terms']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'form-check-input' if name == 'accept_terms' else 'form-control')


class TenderAILoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'already_logged_in': 'This account is already logged in on another device. Ask the admin to mark the user as Pro or log out from the other device first.',
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_superuser:
            return
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.is_pro:
            return
        session_key = profile.active_session_key
        if not session_key:
            return
        if Session.objects.filter(session_key=session_key, expire_date__gt=timezone.now()).exists():
            raise forms.ValidationError(
                self.error_messages['already_logged_in'],
                code='already_logged_in',
            )
        profile.active_session_key = ''
        profile.active_session_started_at = None
        profile.save(update_fields=['active_session_key', 'active_session_started_at'])


class MessageThreadForm(forms.ModelForm):
    first_message = forms.CharField(
        label='Message',
        widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Type your feedback, issue, request, or announcement...'}),
    )

    class Meta:
        model = MessageThread
        fields = ['subject', 'visibility', 'recipient', 'pinned', 'first_message']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['recipient'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['recipient'].required = False
        if not (user and user.is_superuser):
            self.fields['visibility'].choices = [
                (MessageThread.Visibility.ADMIN_ONLY, 'Send privately to admin'),
                (MessageThread.Visibility.PUBLIC, 'Post publicly to all users'),
            ]
            self.fields.pop('recipient')
            self.fields.pop('pinned')
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned = super().clean()
        visibility = cleaned.get('visibility')
        recipient = cleaned.get('recipient')
        if visibility == MessageThread.Visibility.DIRECT and not recipient:
            self.add_error('recipient', 'Choose a user for a direct message.')
        return cleaned


class MessageReplyForm(forms.ModelForm):
    class Meta:
        model = MessagePost
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Write a reply...'}),
        }
        labels = {'body': 'Reply'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['body'].widget.attrs.setdefault('class', 'form-control')


class UserAccessUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['access_days', 'is_pro', 'full_access_until', 'role']
        widgets = {
            'full_access_until': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
        labels = {
            'access_days': 'Access days',
            'is_pro': 'Pro',
            'full_access_until': 'Full access until',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.full_access_until:
            self.fields['full_access_until'].initial = timezone.localtime(self.instance.full_access_until).strftime('%Y-%m-%dT%H:%M')
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'form-select form-select-sm')
            else:
                field.widget.attrs.setdefault('class', 'form-control form-control-sm')
