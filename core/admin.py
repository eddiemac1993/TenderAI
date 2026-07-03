from django.contrib import admin

from .models import Organization, SupportChatMessage, SupportChatSession, SystemSettings, UserProfile


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
    list_display = ('user', 'organization', 'role', 'phone', 'created_at')
    list_filter = ('organization', 'role')
    search_fields = ('user__username', 'user__email', 'organization__name')


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
