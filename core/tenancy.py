from django.conf import settings
from django.urls import resolve

from .models import Organization, UserProfile


DEFAULT_ORGANIZATION_NAME = 'TenderAI Owner'


def default_organization():
    organization, _ = Organization.objects.get_or_create(
        name=DEFAULT_ORGANIZATION_NAME,
        defaults={'active': True},
    )
    return organization


def user_profile(user):
    if not user.is_authenticated:
        return None
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'organization': default_organization() if user.is_superuser else None},
    )
    if user.is_superuser and not profile.organization:
        profile.organization = default_organization()
        profile.save(update_fields=['organization'])
    return profile


def user_organization(user):
    if not user.is_authenticated and not settings.TENDERAI_REQUIRE_LOGIN:
        return default_organization()
    profile = user_profile(user)
    return profile.organization if profile else None


def user_can_manage_users(user):
    if user.is_superuser:
        return True
    profile = user_profile(user)
    return bool(profile and profile.can_manage_users)


def user_has_full_access(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = user_profile(user)
    return bool(profile and profile.has_full_access)


def user_access_status(user):
    if not user.is_authenticated:
        return 'Guest'
    profile = user_profile(user)
    return profile.access_status if profile else 'Limited access'


LIMITED_ACCESS_URL_NAMES = {
    'dashboard',
    'about',
    'login',
    'logout',
    'password_reset',
    'password_reset_done',
    'password_reset_confirm',
    'password_reset_complete',
    'register',
    'tenders:list',
    'tenders:zppa_scrape_today',
    'tenders:zppa_scrape_logs',
    'tenders:zppa_find_by_url',
}


def route_name_for_path(path):
    try:
        match = resolve(path)
    except Exception:
        return ''
    return f'{match.namespace}:{match.url_name}' if match.namespace else (match.url_name or '')


def path_allowed_for_limited_user(path):
    route_name = route_name_for_path(path)
    return route_name in LIMITED_ACCESS_URL_NAMES or path.startswith('/admin/')


def filter_queryset_for_user(queryset, user, organization_field='organization'):
    if not user.is_authenticated:
        if not settings.TENDERAI_REQUIRE_LOGIN:
            return queryset
        return queryset.none()
    if user.is_superuser:
        return queryset
    organization = user_organization(user)
    if not organization:
        return queryset.none()
    return queryset.filter(**{organization_field: organization})
