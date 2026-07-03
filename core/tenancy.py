from django.conf import settings

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
