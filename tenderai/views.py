from datetime import timedelta

from django.db import models
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.views.generic import TemplateView

from companies.models import Company
from core.tenancy import filter_queryset_for_user
from documents.models import CompanyDocument
from tenders.models import Tender, TenderMatch


class DashboardView(TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        soon = today + timedelta(days=14)
        seven_days = today + timedelta(days=7)
        thirty_days = today + timedelta(days=30)
        tenders = Tender.objects.all()
        companies = filter_queryset_for_user(Company.objects.all(), self.request.user)
        documents = filter_queryset_for_user(CompanyDocument.objects.select_related('company'), self.request.user, 'company__organization')
        matches = filter_queryset_for_user(TenderMatch.objects.select_related('tender', 'company'), self.request.user, 'company__organization')
        bid_security_tenders = [t for t in tenders if 'bid secur' in f'{t.description} {t.zppa_details}'.lower()]
        site_visit_tenders = [t for t in tenders if 'site visit' in f'{t.description} {t.zppa_details}'.lower()]
        context.update({
            'company_count': companies.count(),
            'total_tenders': Tender.objects.count(),
            'latest_tenders': Tender.objects.annotate(latest_at=Coalesce('published_at', 'created_at')).order_by('-latest_at', '-id')[:6],
            'closing_7_days': Tender.objects.filter(closing_date__gte=today, closing_date__lte=seven_days).order_by('closing_date')[:8],
            'closing_soon': Tender.objects.filter(closing_date__gte=today, closing_date__lte=soon).order_by('closing_date')[:8],
            'expired_documents': documents.filter(expiry_date__lt=today)[:10],
            'expiring_documents': documents.filter(expiry_date__gte=today, expiry_date__lte=thirty_days).order_by('expiry_date')[:10],
            'best_matches': matches.order_by('-score')[:8],
            'bid_security_tenders': bid_security_tenders[:8],
            'site_visit_tenders': site_visit_tenders[:8],
            'incomplete_companies': companies.filter(
                models.Q(tpin='') | models.Q(address='') | models.Q(email='') | models.Q(phone='')
            )[:8],
        })
        return context


class AboutView(TemplateView):
    template_name = 'about.html'
