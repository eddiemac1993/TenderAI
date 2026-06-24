from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import CompanyForm
from .models import Company


class CompanyListView(ListView):
    model = Company
    template_name = 'companies/company_list.html'
    context_object_name = 'companies'


class CompanyDetailView(DetailView):
    model = Company
    template_name = 'companies/company_detail.html'


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

# Create your views here.
