from django.db import models
from django.urls import reverse
from django.conf import settings

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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['organization__name', 'user__username']

    def __str__(self):
        return f'{self.user.username} - {self.organization or "No organization"}'

    @property
    def can_manage_users(self):
        return self.role == self.Role.ORG_ADMIN or self.user.is_superuser


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
