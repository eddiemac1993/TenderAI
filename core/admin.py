from django.contrib import admin
from django.utils import timezone

from .models import MessagePost, MessageThread, Organization, SupportChatMessage, SupportChatSession, SystemSettings, UserProfile


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('default_tax_type', 'default_validity_period_days', 'default_prepared_by_name', 'default_currency', 'updated_at')


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'district', 'province', 'active', 'created_at')
    list_filter = ('active', 'province')
    search_fields = ('name', 'district', 'province', 'contact_email')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'role', 'access_status', 'is_pro', 'access_days', 'access_expires_at', 'terms_accepted_at', 'phone', 'created_at')
    list_filter = ('organization', 'role', 'is_pro', 'access_days', 'full_access_until')
    search_fields = ('user__username', 'user__email', 'organization__name')
    readonly_fields = ('access_granted_at', 'active_session_key', 'active_session_started_at', 'terms_accepted_at', 'created_at')
    actions = ('grant_7_days', 'grant_30_days', 'revoke_full_access')
    fieldsets = (
        ('User and organization', {
            'fields': ('user', 'organization', 'role', 'phone'),
        }),
        ('Access control', {
            'fields': ('is_pro', 'access_days', 'access_granted_at', 'full_access_until', 'active_session_key', 'active_session_started_at'),
            'description': 'Enter access_days for paid access duration, or mark is_pro to allow full access and multiple devices. full_access_until is optional for a fixed expiry date.',
        }),
        ('Audit', {
            'fields': ('terms_accepted_at', 'created_at'),
        }),
    )

    @admin.action(description='Grant full access for 7 days')
    def grant_7_days(self, request, queryset):
        self.grant_days(queryset, 7)

    @admin.action(description='Grant full access for 30 days')
    def grant_30_days(self, request, queryset):
        self.grant_days(queryset, 30)

    @admin.action(description='Revoke full access and Pro')
    def revoke_full_access(self, request, queryset):
        queryset.update(is_pro=False, access_days=0, access_granted_at=None, full_access_until=None)

    def grant_days(self, queryset, days):
        now = timezone.now()
        for profile in queryset:
            if not profile.access_granted_at:
                profile.access_granted_at = now
            profile.access_days = max(profile.access_days, 0) + days
            profile.save(update_fields=['access_days', 'access_granted_at'])


class SupportChatMessageInline(admin.TabularInline):
    model = SupportChatMessage
    extra = 0
    readonly_fields = ('sender', 'message', 'confidence', 'created_at')
    can_delete = False


@admin.register(SupportChatSession)
class SupportChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_name', 'user_email', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user_name', 'user_email', 'messages__message')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [SupportChatMessageInline]


@admin.register(SupportChatMessage)
class SupportChatMessageAdmin(admin.ModelAdmin):
    list_display = ('session', 'sender', 'confidence', 'created_at')
    list_filter = ('sender', 'created_at')
    search_fields = ('message', 'session__user_name', 'session__user_email')
    readonly_fields = ('created_at',)


class MessagePostInline(admin.TabularInline):
    model = MessagePost
    extra = 0
    readonly_fields = ('author', 'body', 'created_at')
    can_delete = False


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = ('subject', 'visibility', 'created_by', 'recipient', 'pinned', 'closed', 'updated_at')
    list_filter = ('visibility', 'pinned', 'closed', 'created_at')
    search_fields = ('subject', 'posts__body', 'created_by__username', 'recipient__username')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [MessagePostInline]


@admin.register(MessagePost)
class MessagePostAdmin(admin.ModelAdmin):
    list_display = ('thread', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('body', 'thread__subject', 'author__username')
    readonly_fields = ('created_at',)
