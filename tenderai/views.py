from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.views.generic import TemplateView

from companies.models import Company
from documents.models import CompanyDocument
from tenders.models import Tender, TenderMatch


class DashboardView(TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        soon = today + timedelta(days=14)
        seven_days = today + timedelta(days=7)
        tenders = Tender.objects.all()
        bid_security_tenders = [t for t in tenders if 'bid secur' in f'{t.description} {t.zppa_details}'.lower()]
        site_visit_tenders = [t for t in tenders if 'site visit' in f'{t.description} {t.zppa_details}'.lower()]
        context.update({
            'company_count': Company.objects.count(),
            'total_tenders': Tender.objects.count(),
            'closing_7_days': Tender.objects.filter(closing_date__gte=today, closing_date__lte=seven_days).order_by('closing_date')[:8],
            'closing_soon': Tender.objects.filter(closing_date__gte=today, closing_date__lte=soon).order_by('closing_date')[:8],
            'expired_documents': CompanyDocument.objects.filter(expiry_date__lt=today).select_related('company')[:10],
            'best_matches': TenderMatch.objects.select_related('tender', 'company').order_by('-score')[:8],
            'bid_security_tenders': bid_security_tenders[:8],
            'site_visit_tenders': site_visit_tenders[:8],
            'incomplete_companies': Company.objects.filter(
                models.Q(tpin='') | models.Q(address='') | models.Q(email='') | models.Q(phone='')
            )[:8],
        })
        return context
