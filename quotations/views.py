from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.models import SystemSettings

from .forms import InvoiceForm, InvoiceItemForm, QuotationForm, QuotationItemForm
from .models import Invoice, InvoiceItem, Quotation, QuotationItem
from .exports import pdf_http_response


class QuotationListView(ListView):
    model = Quotation
    template_name = 'quotations/quotation_list.html'
    context_object_name = 'quotations'


class QuotationDetailView(DetailView):
    model = Quotation
    template_name = 'quotations/quotation_detail.html'


class QuotationCreateView(CreateView):
    model = Quotation
    form_class = QuotationForm
    template_name = 'form.html'

    def get_initial(self):
        settings = SystemSettings.load()
        initial = super().get_initial()
        initial.update({
            'validity_period_days': settings.default_validity_period_days,
            'tax_type': settings.default_tax_type,
        })
        return initial


class QuotationUpdateView(UpdateView):
    model = Quotation
    form_class = QuotationForm
    template_name = 'form.html'


class QuotationDeleteView(DeleteView):
    model = Quotation
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('quotations:quotation_list')


class QuotationItemCreateView(CreateView):
    model = QuotationItem
    form_class = QuotationItemForm
    template_name = 'form.html'

    def get_success_url(self):
        return self.object.quotation.get_absolute_url()


class InvoiceListView(ListView):
    model = Invoice
    template_name = 'quotations/invoice_list.html'
    context_object_name = 'invoices'


class InvoiceDetailView(DetailView):
    model = Invoice
    template_name = 'quotations/invoice_detail.html'


class InvoiceCreateView(CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'form.html'

    def get_initial(self):
        settings = SystemSettings.load()
        initial = super().get_initial()
        initial.update({'tax_type': settings.default_tax_type})
        return initial


class InvoiceUpdateView(UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'form.html'


class InvoiceDeleteView(DeleteView):
    model = Invoice
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('quotations:invoice_list')


class InvoiceItemCreateView(CreateView):
    model = InvoiceItem
    form_class = InvoiceItemForm
    template_name = 'form.html'

    def get_success_url(self):
        return self.object.invoice.get_absolute_url()


def pdf_placeholder(request, doc_type, pk):
    if doc_type == 'quotation':
        document = Quotation.objects.get(pk=pk)
        return pdf_http_response(document, 'Quotation', f'quotation-{document.number}.pdf')
    document = Invoice.objects.get(pk=pk)
    return pdf_http_response(document, 'Invoice', f'invoice-{document.number}.pdf')

# Create your views here.
