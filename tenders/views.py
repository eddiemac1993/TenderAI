import json
import os
from datetime import timedelta
from pathlib import Path

from django.contrib import messages
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from ai_engine.forms import SolicitationDocumentForm, TenderChatForm
from ai_engine.models import SolicitationDocument, TenderChatMessage
from ai_engine.services import PlaceholderTenderAnalysisService
from ai_engine.services import answer_tender_question
from ai_engine.services import process_solicitation_document
from bid_generator.services import document_gap_rows_for_company, expanded_tender_xml_items, xml_required_document_evidence
from companies.models import BusinessCategory, Company
from core.tenancy import filter_queryset_for_user, user_organization
from documents.models import CompanyDocument

from .forms import BidTaskForm, TenderForm, TenderRequirementForm, ZppaJsonImportForm, ZppaManualImportForm, ZppaUrlImportForm
from .models import BidTask, Tender, TenderMatch, TenderRequirement, ZppaScrapeLog
from .pdf_exports import generate_xml_structure_pdf
from .services import (
    bid_task_progress,
    calculate_tender_matches,
    ensure_bid_tasks,
    required_document_types,
    tender_decisions,
    tender_signals,
    tender_workspace_tree,
)
from .zppa_documents import PublicZppaDocumentFetcher
from .zppa_scraper import bid_security_amount_from_detail_rows, import_public_zppa_tender_from_url, import_public_zppa_tenders, payment_amount_from_detail_rows


ALLOWED_TENDER_UPLOAD_EXTENSIONS = ('.pdf', '.docx', '.xml', '.txt')


def analyze_uploaded_tender_files(tender, uploaded_files):
    analyzed_count = 0
    skipped = []
    created_tasks = 0
    required_signals = 0
    for uploaded_file in uploaded_files:
        if not uploaded_file.name.lower().endswith(ALLOWED_TENDER_UPLOAD_EXTENSIONS):
            skipped.append(uploaded_file.name)
            continue
        document = SolicitationDocument(tender=tender)
        document.file.save(uploaded_file.name, uploaded_file, save=True)
        analysis = process_solicitation_document(document)
        analyzed_count += 1
        created_tasks += int(analysis.get('bid_tasks_created') or 0)
        required_signals += len(analysis.get('required_documents', []))
    return {
        'analyzed_count': analyzed_count,
        'skipped': skipped,
        'created_tasks': created_tasks,
        'required_signals': required_signals,
    }


def add_tender_upload_messages(request, result):
    if result['analyzed_count']:
        messages.success(
            request,
            f'Uploaded and analyzed {result["analyzed_count"]} tender file(s). '
            f'Found {result["required_signals"]} required document signal(s).',
        )
        if result['created_tasks']:
            messages.info(request, f'Created {result["created_tasks"]} bid task(s) from the uploaded files.')
    if result['skipped']:
        messages.warning(request, 'Skipped unsupported file(s): ' + ', '.join(result['skipped'][:5]))


def title_from_uploaded_files(uploaded_files):
    for uploaded_file in uploaded_files:
        stem = Path(uploaded_file.name).stem.replace('_', ' ').replace('-', ' ').strip()
        if stem:
            return stem[:220]
    return 'Limited tender from uploaded files'


class TenderListView(ListView):
    model = Tender
    template_name = 'tenders/tender_list.html'
    context_object_name = 'tenders'

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .annotate(latest_at=Coalesce('published_at', 'created_at'))
        )
        queryset = self.apply_filters(queryset)
        return queryset.order_by('-latest_at', '-id')

    def apply_filters(self, queryset):
        query = self.request.GET.get('q', '').strip()
        entity = self.request.GET.get('entity', '').strip()
        period = self.request.GET.get('period', '').strip()
        today = timezone.localdate()
        now = timezone.now()

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(tender_number__icontains=query)
                | Q(zppa_resource_id__icontains=query)
                | Q(procuring_entity__icontains=query)
                | Q(description__icontains=query)
                | Q(procurement_method__icontains=query)
            )
        if entity:
            queryset = queryset.filter(procuring_entity__icontains=entity)
        if period == 'published_today':
            queryset = queryset.filter(published_at__date=today)
        elif period == 'published_7':
            queryset = queryset.filter(published_at__date__gte=today - timedelta(days=7))
        elif period == 'open':
            queryset = queryset.filter(
                Q(closing_at__gte=now)
                | Q(closing_date__gte=today)
                | (Q(closing_at__isnull=True) & Q(closing_date__isnull=True))
            )
        elif period == 'closing_today':
            queryset = queryset.filter(Q(closing_at__date=today) | Q(closing_date=today))
        elif period == 'closing_7':
            queryset = queryset.filter(
                Q(closing_at__date__gte=today, closing_at__date__lte=today + timedelta(days=7))
                | Q(closing_date__gte=today, closing_date__lte=today + timedelta(days=7))
            )
        elif period == 'closing_30':
            queryset = queryset.filter(
                Q(closing_at__date__gte=today, closing_at__date__lte=today + timedelta(days=30))
                | Q(closing_date__gte=today, closing_date__lte=today + timedelta(days=30))
            )
        elif period == 'already_closed':
            queryset = queryset.filter(Q(closing_at__lt=now) | Q(closing_date__lt=today))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filtered_queryset = self.apply_filters(
            Tender.objects.annotate(latest_at=Coalesce('published_at', 'created_at'))
        )
        context['selected_query'] = self.request.GET.get('q', '').strip()
        context['selected_entity'] = self.request.GET.get('entity', '').strip()
        context['selected_period'] = self.request.GET.get('period', '').strip()
        context['entity_options'] = (
            Tender.objects.exclude(procuring_entity='')
            .order_by('procuring_entity')
            .values_list('procuring_entity', flat=True)
            .distinct()
        )
        context['period_options'] = [
            ('', 'All periods'),
            ('open', 'Open / not yet closed'),
            ('published_today', 'Published today'),
            ('published_7', 'Published last 7 days'),
            ('closing_today', 'Closing today'),
            ('closing_7', 'Closing in 7 days'),
            ('closing_30', 'Closing in 30 days'),
            ('already_closed', 'Already closed'),
        ]
        context['filtered_count'] = filtered_queryset.count()
        context['open_national_count'] = filtered_queryset.filter(procurement_method__icontains='Open Bidding National').count()
        context['entity_count'] = filtered_queryset.exclude(procuring_entity='').values('procuring_entity').distinct().count()
        return context


class TenderDetailView(DetailView):
    model = Tender
    template_name = 'tenders/tender_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['solicitation_form'] = SolicitationDocumentForm()
        context['chat_form'] = TenderChatForm()
        context['chat_messages'] = self.object.chat_messages.select_related('solicitation_document')[:8]
        organization = user_organization(self.request.user) if not self.request.user.is_superuser else None
        matches = calculate_tender_matches(self.object, organization=organization)
        decisions = tender_decisions(self.object, matches)
        context['best_decision'] = decisions[0] if decisions else None
        context['top_decisions'] = decisions[:4]
        context['xml_evidence_summary'] = xml_required_document_evidence(self.object)
        expanded_xml_items = expanded_tender_xml_items(self.object)
        context['expanded_xml_items'] = expanded_xml_items
        if decisions:
            best_company = decisions[0]['match'].company
            context['best_company_document_gaps'] = document_gap_rows_for_company(self.object, best_company)
            context['best_company_for_uploads'] = best_company
        selected_company = None
        selected_company_id = self.request.GET.get('company')
        if selected_company_id:
            selected_company = filter_queryset_for_user(Company.objects.all(), self.request.user).filter(pk=selected_company_id).first()
        context['workspace_selected_company'] = selected_company
        context['workspace_tree'] = tender_workspace_tree(self.object, expanded_xml_items, selected_company)
        context['required_document_labels'] = [
            CompanyDocument.DocumentType(doc_type).label for doc_type in required_document_types(self.object)
        ]
        context['tender_signals'] = tender_signals(self.object)
        context['bid_task_progress'] = bid_task_progress(self.object)
        context['bid_company_options'] = filter_queryset_for_user(Company.objects.order_by('name'), self.request.user)
        return context


@require_POST
def save_tender_workspace(request, pk):
    tender = get_object_or_404(Tender, pk=pk)
    ensure_bid_tasks(tender)
    if tender.status == Tender.Status.NEW:
        tender.status = Tender.Status.REVIEWING
        tender.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Tender saved to Draft Tenders. Open it when you are ready to select a company and prepare documents.')
    return redirect(tender)


class TenderFileUploadView(DetailView):
    model = Tender
    template_name = 'tenders/tender_file_upload.html'
    context_object_name = 'tender'

    def post(self, request, *args, **kwargs):
        tender = self.get_object()
        uploaded_files = request.FILES.getlist('files')
        if not uploaded_files:
            messages.error(request, 'Please choose at least one PDF, DOCX, XML, or text file.')
            return redirect('tenders:upload_files', pk=tender.pk)

        result = analyze_uploaded_tender_files(tender, uploaded_files)
        add_tender_upload_messages(request, result)
        return redirect(tender)


class TenderFileUploadChooserView(TemplateView):
    template_name = 'tenders/tender_file_upload_choose.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tender_options'] = Tender.objects.annotate(
            latest_at=Coalesce('published_at', 'created_at')
        ).order_by('-latest_at', '-id')[:250]
        return context

    def post(self, request, *args, **kwargs):
        upload_mode = request.POST.get('upload_mode', 'quick')
        tender_id = request.POST.get('tender')
        uploaded_files = request.FILES.getlist('files')
        if not uploaded_files:
            messages.error(request, 'Please choose at least one PDF, DOCX, XML, or text file.')
            return redirect('tenders:upload_files_choose')

        if upload_mode == 'existing':
            if not tender_id:
                messages.error(request, 'Please choose the tender these files belong to.')
                return redirect('tenders:upload_files_choose')
            tender = get_object_or_404(Tender, pk=tender_id)
        else:
            tender = Tender.objects.create(
                title=title_from_uploaded_files(uploaded_files),
                procuring_entity='Limited ZPPA tender',
                source=Tender.Source.MANUAL,
                status=Tender.Status.NEW,
                notes='Limited/manual tender created from uploaded solicitation/XML files.',
            )

        result = analyze_uploaded_tender_files(tender, uploaded_files)
        add_tender_upload_messages(request, result)
        return redirect(tender)


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


class ZppaJsonImportView(FormView):
    template_name = 'tenders/zppa_json_import.html'
    form_class = ZppaJsonImportForm
    success_url = reverse_lazy('tenders:list')

    def form_valid(self, form):
        payload = json.load(form.cleaned_data['file'])
        created_count = 0
        updated_count = 0
        for item in payload:
            tender, created = upsert_zppa_import_item(item)
            created_count += int(created)
            updated_count += int(not created)
        messages.success(self.request, f'Imported ZPPA JSON: {created_count} created, {updated_count} updated.')
        return super().form_valid(form)


class ZppaUrlImportView(FormView):
    template_name = 'tenders/zppa_url_import.html'
    form_class = ZppaUrlImportForm

    def form_valid(self, form):
        url = form.cleaned_data['url']
        try:
            tender, created = import_public_zppa_tender_from_url(url)
        except Exception as exc:
            messages.error(self.request, f'TenderAI could not import that public ZPPA URL: {exc}')
            return self.form_invalid(form)

        messages.success(self.request, f'{"Imported" if created else "Updated"} tender from ZPPA URL.')
        if form.cleaned_data.get('fetch_documents'):
            try:
                fetched, skipped = PublicZppaDocumentFetcher().fetch_all_for_tender(tender)
                messages.success(self.request, f'Fetched and analyzed {len(fetched)} public ZPPA document(s).')
                if skipped:
                    messages.warning(self.request, 'Some public documents could not be fetched: ' + ' | '.join(skipped[:3]))
            except Exception as exc:
                messages.warning(self.request, f'Tender imported, but public documents could not be fetched: {exc}')
        return redirect(tender)


class TenderMatchView(TemplateView):
    template_name = 'tenders/matching.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tender = get_object_or_404(Tender, pk=self.kwargs['pk'])
        context['tender'] = tender
        organization = user_organization(self.request.user) if not self.request.user.is_superuser else None
        matches = calculate_tender_matches(tender, organization=organization)
        context['matches'] = matches
        context['decisions'] = tender_decisions(tender, matches)
        return context


class BidTaskListView(TemplateView):
    template_name = 'tenders/bid_tasks.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tender = get_object_or_404(Tender, pk=self.kwargs['pk'])
        context['tender'] = tender
        context['progress'] = bid_task_progress(tender)
        context['task_form'] = BidTaskForm(initial={'due_date': tender.deadline_date})
        return context


class BidTaskCreateView(CreateView):
    model = BidTask
    form_class = BidTaskForm
    template_name = 'tenders/bid_task_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.tender = get_object_or_404(Tender, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.tender = self.tender
        form.instance.sort_order = 500
        messages.success(self.request, 'Bid task added.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tender'] = self.tender
        return context

    def get_success_url(self):
        return reverse('tenders:tasks', args=[self.tender.pk])


@require_POST
def update_bid_task_status(request, pk, task_id):
    tender = get_object_or_404(Tender, pk=pk)
    task = get_object_or_404(BidTask, pk=task_id, tender=tender)
    status = request.POST.get('status')
    if status in BidTask.Status.values:
        task.status = status
        task.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Task updated: {task.title}.')
    else:
        messages.error(request, 'Invalid task status.')
    return redirect(request.POST.get('next') or reverse('tenders:tasks', args=[tender.pk]))


def upsert_zppa_import_item(item):
    lookup = {}
    if item.get('resource_id'):
        lookup['zppa_resource_id'] = item['resource_id']
    elif item.get('tender_number'):
        lookup['tender_number'] = item['tender_number']
    else:
        lookup = {'title': item['title'], 'imported_reference': item.get('url', '')}
    closing_at = parse_datetime(item.get('closing_at') or '')
    published_at = parse_datetime(item.get('published_at') or '')
    detail_rows = item.get('detail_rows') or []
    participation_fee = payment_amount_from_detail_rows(detail_rows)
    bid_security_amount = bid_security_amount_from_detail_rows(detail_rows)
    tender, created = Tender.objects.update_or_create(
        **lookup,
        defaults={
            'title': item.get('title', ''),
            'tender_number': item.get('tender_number', ''),
            'zppa_resource_id': item.get('resource_id', ''),
            'procuring_entity': item.get('procuring_entity') or 'ZPPA e-GP public listing',
            'description': item.get('description', ''),
            'source': Tender.Source.ZPPA,
            'closing_date': closing_at.date() if closing_at else None,
            'published_at': published_at,
            'closing_at': closing_at,
            'submission_method': item.get('submission_method', ''),
            'procurement_method': item.get('procurement_method', ''),
            'bid_security_amount': bid_security_amount,
            'participation_fee': participation_fee,
            'zppa_details': detail_rows,
            'imported_reference': item.get('url', ''),
            'notes': f'Imported from ZPPA JSON export. Listed date: {item.get("listed_date") or "unknown"}.',
        },
    )
    return tender, created


def analyze_tender_placeholder(request, pk):
    tender = get_object_or_404(Tender, pk=pk)
    service = PlaceholderTenderAnalysisService()
    created = service.analyze_tender(tender)
    messages.success(request, f'Placeholder AI analysis added {created} requirement(s).')
    return HttpResponseRedirect(reverse('tenders:detail', args=[pk]))


def scrape_zppa_today(request):
    try:
        imported = import_public_zppa_tenders(today_only=False, limit=200, write_log=True)
    except Exception as exc:
        messages.error(request, zppa_scrape_error_message(exc))
        return HttpResponseRedirect(reverse('tenders:zppa_scrape_logs'))
    created_count = sum(1 for _, created in imported if created)
    updated_count = len(imported) - created_count
    messages.success(
        request,
        f'Public ZPPA scrape finished: {created_count} created, {updated_count} updated from open/not-yet-closed public listings.',
    )
    return HttpResponseRedirect(f'{reverse("tenders:list")}?period=open')


def zppa_scrape_error_message(exc):
    detail = str(exc)
    lower = detail.lower()
    if 'tunnel connection failed: 403' in lower or os.environ.get('PYTHONANYWHERE_DOMAIN'):
        reason = 'PythonAnywhere free accounts may block outbound access to some public sites.'
    elif 'getaddrinfo failed' in lower:
        reason = 'Your local machine could not resolve the ZPPA website address. Check internet/DNS, then try again.'
    elif 'timed out' in lower or 'timeout' in lower:
        reason = 'The ZPPA public site did not respond before the local timeout. This can happen when the site is slow or temporarily unavailable.'
    else:
        reason = 'The public ZPPA site could not be reached from this machine.'
    return f'ZPPA scrape could not run. {reason} The failure was logged: {detail}'


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
        if analysis.get('bid_tasks_created'):
            messages.info(request, f'Created {analysis["bid_tasks_created"]} bid task(s) from the solicitation analysis.')
    else:
        messages.error(request, 'Could not upload solicitation document. Please choose a PDF, DOCX, XML, or text file.')
    return redirect(tender)


@require_POST
def fetch_zppa_solicitation_document(request, pk):
    tender = get_object_or_404(Tender, pk=pk)
    try:
        solicitation, public_document, analysis = PublicZppaDocumentFetcher().fetch_for_tender(tender)
    except Exception as exc:
        messages.error(
            request,
            f'Could not fetch a public ZPPA solicitation document: {exc}',
        )
        return redirect(tender)
    messages.success(
        request,
        f'Fetched and analyzed public ZPPA document: {public_document.filename}. '
        f'Found {len(analysis.get("required_documents", []))} required document signal(s).',
    )
    if analysis.get('bid_tasks_created'):
        messages.info(request, f'Created {analysis["bid_tasks_created"]} bid task(s) from the solicitation analysis.')
    return redirect(tender)


@require_POST
def fetch_zppa_all_public_documents(request, pk):
    tender = get_object_or_404(Tender, pk=pk)
    try:
        fetched, skipped = PublicZppaDocumentFetcher().fetch_all_for_tender(tender)
    except Exception as exc:
        messages.error(
            request,
            f'Could not fetch public ZPPA documents: {exc}',
        )
        return redirect(tender)

    document_names = ', '.join(public_doc.filename for _, public_doc, _ in fetched[:5])
    messages.success(
        request,
        f'Fetched and analyzed {len(fetched)} public ZPPA document(s): {document_names}.',
    )
    created_tasks = sum(analysis.get('bid_tasks_created', 0) for _, _, analysis in fetched)
    if created_tasks:
        messages.info(request, f'Created {created_tasks} bid task(s) from the downloaded documents.')
    if skipped:
        messages.warning(
            request,
            'Some ZPPA documents could not be downloaded publicly. They may require payment or login: '
            + ' | '.join(skipped[:3])
        )
    return redirect(tender)


def download_xml_structure_pdf(request, pk):
    tender = get_object_or_404(Tender, pk=pk)
    pdf_bytes = generate_xml_structure_pdf(tender)
    filename = f'xml-structure-{tender.pk}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    disposition = 'inline' if request.GET.get('inline') == '1' else 'attachment'
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


def ask_tender_chatbot(request, pk):
    tender = get_object_or_404(Tender, pk=pk)
    if request.method != 'POST':
        return redirect(tender)
    form = TenderChatForm(request.POST)
    if form.is_valid():
        question = form.cleaned_data['question']
        answer, document = answer_tender_question(tender, question)
        TenderChatMessage.objects.create(
            tender=tender,
            solicitation_document=document,
            question=question,
            answer=answer,
        )
        messages.success(request, 'TenderAI answered your question from the uploaded solicitation document.')
    else:
        messages.error(request, 'Please type a question for TenderAI.')
    return redirect(tender)
