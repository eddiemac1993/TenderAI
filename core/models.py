from django.db import models
from django.urls import reverse
from django.conf import settings
from django.utils import timezone

from quotations.models import TaxType


class Organization(models.Model):
    name = models.CharField(max_length=180, unique=True)
    province = models.CharField(max_length=120, blank=True)
    district = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=60, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ORG_ADMIN = 'ORG_ADMIN', 'Organization Admin'
        STAFF = 'STAFF', 'Staff'
        VIEWER = 'VIEWER', 'Viewer'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='members', null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
    phone = models.CharField(max_length=60, blank=True)
    is_pro = models.BooleanField(default=False, help_text='Pro users can use TenderAI on multiple devices at the same time.')
    access_days = models.PositiveIntegerField(default=0, help_text='Number of full-access days granted by admin. Use 0 for limited access.')
    access_granted_at = models.DateTimeField(null=True, blank=True)
    full_access_until = models.DateTimeField(null=True, blank=True, help_text='Leave blank for limited access unless the user is Pro.')
    active_session_key = models.CharField(max_length=80, blank=True)
    active_session_started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['organization__name', 'user__username']

    def __str__(self):
        return f'{self.user.username} - {self.organization or "No organization"}'

    @property
    def can_manage_users(self):
        return self.role == self.Role.ORG_ADMIN or self.user.is_superuser

    @property
    def has_full_access(self):
        if self.user.is_superuser:
            return True
        if self.is_pro:
            return True
        expiry = self.access_expires_at
        return bool(expiry and expiry >= timezone.now())

    @property
    def access_expires_at(self):
        expiries = []
        if self.full_access_until:
            expiries.append(self.full_access_until)
        if self.access_days and self.access_granted_at:
            expiries.append(self.access_granted_at + timezone.timedelta(days=self.access_days))
        return max(expiries) if expiries else None

    @property
    def access_status(self):
        if self.user.is_superuser:
            return 'Superuser'
        if self.is_pro:
            return 'Pro'
        if self.has_full_access:
            return f'Full access until {timezone.localtime(self.access_expires_at):%d/%m/%Y %H:%M}'
        return 'Limited access'

    def save(self, *args, **kwargs):
        if self.access_days and not self.access_granted_at:
            self.access_granted_at = timezone.now()
        if not self.access_days:
            self.access_granted_at = None
        super().save(*args, **kwargs)


class SystemSettings(models.Model):
    default_tax_type = models.CharField(max_length=10, choices=TaxType.choices, default=TaxType.NONE)
    default_validity_period_days = models.PositiveIntegerField(default=30)
    default_prepared_by_name = models.CharField(max_length=120, blank=True)
    default_currency = models.CharField(max_length=20, default='ZMW')
    letterhead = models.FileField(upload_to='settings/letterheads/', blank=True)
    signature = models.FileField(upload_to='settings/signatures/', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'system settings'
        verbose_name_plural = 'system settings'

    def __str__(self):
        return 'TenderAI system settings'

    @classmethod
    def load(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings


class SupportChatSession(models.Model):
    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        SATISFIED = 'SATISFIED', 'Satisfied'
        NEEDS_ADMIN = 'NEEDS_ADMIN', 'Needs admin clarification'
        CLOSED = 'CLOSED', 'Closed'

    user_name = models.CharField(max_length=120, blank=True)
    user_email = models.EmailField(blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_chats')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        label = self.user_name or self.user_email or f'Guest #{self.pk}'
        return f'Support chat - {label}'

    def get_absolute_url(self):
        return reverse('core:support_chat_detail', args=[self.pk])


class SupportChatMessage(models.Model):
    class Sender(models.TextChoices):
        USER = 'USER', 'User'
        AI = 'AI', 'TenderAI assistant'
        ADMIN = 'ADMIN', 'Admin'

    session = models.ForeignKey(SupportChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10, choices=Sender.choices)
    message = models.TextField()
    confidence = models.PositiveSmallIntegerField(default=70)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.get_sender_display()} - {self.created_at:%d/%m/%Y %H:%M}'


class MessageThread(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = 'PUBLIC', 'Public to all users'
        ADMIN_ONLY = 'ADMIN_ONLY', 'Only admin can view'
        DIRECT = 'DIRECT', 'Direct message'

    subject = models.CharField(max_length=180)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_threads')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_message_threads', null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, related_name='message_threads', null=True, blank=True)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.ADMIN_ONLY)
    pinned = models.BooleanField(default=False)
    closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-pinned', '-updated_at']

    def __str__(self):
        return self.subject

    @property
    def is_public(self):
        return self.visibility == self.Visibility.PUBLIC

    def get_absolute_url(self):
        return reverse('core:message_thread_detail', args=[self.pk])


class MessagePost(models.Model):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_posts')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.author} - {self.created_at:%d/%m/%Y %H:%M}'
