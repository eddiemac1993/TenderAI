from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from ai_engine.forms import SolicitationDocumentForm
from ai_engine.models import SolicitationDocument
from ai_engine.services import PlaceholderTenderAnalysisService
from ai_engine.services import process_solicitation_document
from companies.models import BusinessCategory, Company
from documents.models import CompanyDocument

from .forms import TenderForm, TenderRequirementForm, ZppaManualImportForm
from .models import Tender, TenderMatch, TenderRequirement, ZppaScrapeLog
from .services import calculate_tender_matches
from .zppa_scraper import import_public_zppa_tenders


class TenderListView(ListView):
    model = Tender
    template_name = 'tenders/tender_list.html'
    context_object_name = 'tenders'


class TenderDetailView(DetailView):
    model = Tender
    template_name = 'tenders/tender_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['solicitation_form'] = SolicitationDocumentForm()
        return context


class TenderCreateView(CreateView):
    model = Tender
    form_class = TenderForm
    template_name = 'form.html'


class TenderUpdateView(UpdateView):
    model = Tender
    form_class = TenderForm
    template_name = 'form.html'


class TenderDeleteView(DeleteView):
    model = Tender
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('tenders:list')


class RequirementListView(ListView):
    model = TenderRequirement
    template_name = 'tenders/requirement_list.html'
    context_object_name = 'requirements'

    def get_queryset(self):
        qs = super().get_queryset().select_related('tender')
        tender_id = self.kwargs.get('tender_id')
        return qs.filter(tender_id=tender_id) if tender_id else qs


class RequirementCreateView(CreateView):
    model = TenderRequirement
    form_class = TenderRequirementForm
    template_name = 'form.html'

    def get_initial(self):
        initial = super().get_initial()
        if self.kwargs.get('tender_id'):
            initial['tender'] = self.kwargs['tender_id']
        return initial

    def get_success_url(self):
        return reverse('tenders:detail', args=[self.object.tender_id])


class ZppaManualImportView(FormView):
    template_name = 'tenders/zppa_import.html'
    form_class = ZppaManualImportForm

    def form_valid(self, form):
        category = None
        category_name = form.cleaned_data.get('category_name')
        if category_name:
            category, _ = BusinessCategory.objects.get_or_create(name=category_name)
        tender = Tender.objects.create(
            title=form.cleaned_data['title'],
            tender_number=form.cleaned_data.get('tender_number', ''),
            procuring_entity=form.cleaned_data['procuring_entity'],
            source=Tender.Source.ZPPA,
            category=category,
            closing_date=form.cleaned_data.get('closing_date'),
            submission_method=form.cleaned_data.get('submission_method', ''),
            imported_reference=form.cleaned_data.get('source_url_or_reference', ''),
        )
        messages.success(self.request, 'ZPPA tender imported manually.')
        return redirect(tender)


class TenderMatchView(TemplateView):
    template_name = 'tenders/matching.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tender = get_object_or_404(Tender, pk=self.kwargs['pk'])
        context['tender'] = tender
        context['matches'] = calculate_tender_matches(tender)
        return context


def analyze_tender_placeholder(request, pk):
    tender = get_object_or_404(Tender, pk=pk)
    service = PlaceholderTenderAnalysisService()
    created = service.analyze_tender(tender)
    messages.success(request, f'Placeholder AI analysis added {created} requirement(s).')
    return HttpResponseRedirect(reverse('tenders:detail', args=[pk]))


def scrape_zppa_today(request):
    try:
        imported = import_public_zppa_tenders(today_only=True, limit=10, write_log=True)
    except Exception as exc:
        messages.error(
            request,
            'ZPPA scrape could not run from this server. PythonAnywhere free accounts may block outbound access to some public sites. '
            f'The failure was logged: {exc}',
        )
        return HttpResponseRedirect(reverse('tenders:zppa_scrape_logs'))
    created_count = sum(1 for _, created in imported if created)
    updated_count = len(imported) - created_count
    messages.success(
        request,
        f'Public ZPPA scrape finished: {created_count} created, {updated_count} updated.',
    )
    return HttpResponseRedirect(reverse('tenders:list'))


class ZppaScrapeLogListView(ListView):
    model = ZppaScrapeLog
    template_name = 'tenders/scrape_logs.html'
    context_object_name = 'logs'


def upload_solicitation_document(request, pk):
    tender = get_object_or_404(Tender, pk=pk)
    if request.method != 'POST':
        return redirect(tender)
    form = SolicitationDocumentForm(request.POST, request.FILES)
    if form.is_valid():
        document = form.save(commit=False)
        document.tender = tender
        document.save()
        analysis = process_solicitation_document(document)
        messages.success(
            request,
            f'Solicitation uploaded and analyzed. Found {len(analysis.get("required_documents", []))} required document signal(s).',
        )
    else:
        messages.error(request, 'Could not upload solicitation document. Please choose a PDF, DOCX, or text file.')
    return redirect(tender)
