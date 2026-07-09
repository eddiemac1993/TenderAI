from datetime import timedelta

from django.db import models
from django.utils import timezone

from companies.models import Company
from documents.models import CompanyDocument
from tenders.models import Tender
from .tenancy import filter_queryset_for_user, user_can_manage_users, user_organization
from .update_service import get_update_status, web_updates_enabled


def tenderai_alerts(request):
    today = timezone.localdate()
    in_seven_days = today + timedelta(days=7)
    in_thirty_days = today + timedelta(days=30)
    documents = filter_queryset_for_user(CompanyDocument.objects.all(), request.user, 'company__organization')
    companies = filter_queryset_for_user(Company.objects.all(), request.user)

    closing_soon = Tender.objects.filter(
        models.Q(closing_at__date__gte=today, closing_at__date__lte=in_seven_days)
        | models.Q(closing_date__gte=today, closing_date__lte=in_seven_days)
    ).count()
    expiring_documents = documents.filter(
        expiry_date__gte=today,
        expiry_date__lte=in_thirty_days,
    ).count()
    expired_documents = documents.filter(expiry_date__lt=today).count()
    incomplete_profiles = companies.filter(
        models.Q(tpin='') | models.Q(address='') | models.Q(email='') | models.Q(phone='')
    ).count()

    alerts = {
        'closing_soon': closing_soon,
        'expiring_documents': expiring_documents,
        'expired_documents': expired_documents,
        'incomplete_profiles': incomplete_profiles,
    }
    alerts['total'] = sum(alerts.values())
    return {'tenderai_alerts': alerts}


def tenderai_updates(request):
    if not web_updates_enabled():
        return {'tenderai_update': {'enabled': False, 'available': False}}
    return {'tenderai_update': get_update_status(force_fetch=False)}


def tenderai_user_context(request):
    organization = user_organization(request.user) if request.user.is_authenticated else None
    return {
        'tenderai_user': {
            'can_manage_users': user_can_manage_users(request.user) if request.user.is_authenticated else False,
            'organization': organization,
        }
    }
