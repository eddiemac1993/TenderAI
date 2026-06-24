from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import CompanyDocumentForm
from .models import CompanyDocument


class DocumentListView(ListView):
    model = CompanyDocument
    template_name = 'documents/document_list.html'
    context_object_name = 'documents'


class DocumentDetailView(DetailView):
    model = CompanyDocument
    template_name = 'documents/document_detail.html'


class DocumentCreateView(CreateView):
    model = CompanyDocument
    form_class = CompanyDocumentForm
    template_name = 'form.html'


class DocumentUpdateView(UpdateView):
    model = CompanyDocument
    form_class = CompanyDocumentForm
    template_name = 'form.html'


class DocumentDeleteView(DeleteView):
    model = CompanyDocument
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('documents:list')

# Create your views here.
