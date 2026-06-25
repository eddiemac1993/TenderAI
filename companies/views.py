from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from documents.services import sync_company_profile_from_documents

from .forms import CompanyForm
from .models import Company


class CompanyListView(ListView):
    model = Company
    template_name = 'companies/company_list.html'
    context_object_name = 'companies'


class CompanyDetailView(DetailView):
    model = Company
    template_name = 'companies/company_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        missing = []
        for label, value in [
            ('TPIN', self.object.tpin),
            ('PACRA registration number', self.object.registration_number),
            ('Phone', self.object.phone),
            ('Email', self.object.email),
        ]:
            if not value:
                missing.append(label)
        context['missing_profile_fields'] = missing
        return context


class CompanyCreateView(CreateView):
    model = Company
    form_class = CompanyForm
    template_name = 'form.html'


class CompanyUpdateView(UpdateView):
    model = Company
    form_class = CompanyForm
    template_name = 'form.html'


class CompanyDeleteView(DeleteView):
    model = Company
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('companies:list')


@require_POST
def sync_company_profile(request, pk):
    company = get_object_or_404(Company, pk=pk)
    updates = sync_company_profile_from_documents(company)
    if updates:
        messages.success(request, f'Updated company profile fields: {", ".join(updates.keys())}.')
    else:
        messages.warning(
            request,
            'No TPIN or PACRA registration number was found in the uploaded document text. If the PDFs are scanned images, enter profile values manually using Edit.',
        )
    return redirect(company.get_absolute_url())
 
# Create your views here.
