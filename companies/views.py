from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.tenancy import filter_queryset_for_user, user_organization
from documents.services import sync_company_profile_from_documents
from tenders.services import company_profile_gaps, company_readiness

from .forms import CompanyForm
from .models import Company
from .profile_pack import build_company_profile_pack


class CompanyListView(ListView):
    model = Company
    template_name = 'companies/company_list.html'
    context_object_name = 'companies'

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('documents', 'business_categories', 'organization')
        return filter_queryset_for_user(queryset, self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cards = []
        ready_count = 0
        incomplete_count = 0
        for company in context['companies']:
            readiness = company_readiness(company)
            gaps = company_profile_gaps(company)
            if readiness['score'] >= 80 and not gaps:
                ready_count += 1
            if gaps:
                incomplete_count += 1
            cards.append({
                'company': company,
                'readiness': readiness,
                'gaps': gaps,
                'document_count': company.documents.count(),
            })
        context['company_cards'] = cards
        context['ready_company_count'] = ready_count
        context['incomplete_company_count'] = incomplete_count
        return context


class CompanyDetailView(DetailView):
    model = Company
    template_name = 'companies/company_detail.html'

    def get_queryset(self):
        return filter_queryset_for_user(super().get_queryset(), self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['missing_profile_fields'] = company_profile_gaps(self.object)
        context['readiness'] = company_readiness(self.object)
        return context


class CompanyCreateView(CreateView):
    model = Company
    form_class = CompanyForm
    template_name = 'form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.instance.organization = user_organization(self.request.user)
        return super().form_valid(form)


class CompanyUpdateView(UpdateView):
    model = Company
    form_class = CompanyForm
    template_name = 'form.html'

    def get_queryset(self):
        return filter_queryset_for_user(super().get_queryset(), self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class CompanyDeleteView(DeleteView):
    model = Company
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('companies:list')

    def get_queryset(self):
        return filter_queryset_for_user(super().get_queryset(), self.request.user)


@require_POST
def sync_company_profile(request, pk):
    company = get_object_or_404(filter_queryset_for_user(Company.objects.all(), request.user), pk=pk)
    updates = sync_company_profile_from_documents(company)
    if updates:
        messages.success(request, f'Updated company profile fields: {", ".join(updates.keys())}.')
    else:
        messages.warning(
            request,
            'No TPIN or PACRA registration number was found in the uploaded document text. If the PDFs are scanned images, enter profile values manually using Edit.',
        )
    return redirect(company.get_absolute_url())


def download_company_profile_pack(request, pk):
    company = get_object_or_404(filter_queryset_for_user(Company.objects.all(), request.user), pk=pk)
    buffer, filename = build_company_profile_pack(company)
    return FileResponse(buffer, as_attachment=True, filename=filename, content_type='application/pdf')
 
# Create your views here.
