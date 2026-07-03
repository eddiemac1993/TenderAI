from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from core.tenancy import filter_queryset_for_user
from tenders.services import company_readiness, tender_decision
from companies.models import Company
from tenders.models import Tender, TenderMatch

from .forms import BidPackForm
from .models import BidPack
from .services import (
    build_bid_checklist,
    generate_combined_bid_documents_pdf,
    generate_xml_bid_documents,
    document_gap_rows_for_company,
    ordered_certificate_documents,
    ordered_itb_rows,
    regeneration_status,
    save_generated_files,
    submission_gap_items,
    submission_gap_rows,
    xml_bid_structure_groups,
)


class BidPackListView(ListView):
    model = BidPack
    template_name = 'bid_generator/bidpack_list.html'
    context_object_name = 'bidpacks'

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related('tender', 'company')
            .annotate(document_count=Count('bid_documents'))
        )
        return filter_queryset_for_user(queryset, self.request.user, 'company__organization')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        context['generated_count'] = queryset.filter(generated_pdf__gt='', generated_docx__gt='').count()
        context['xml_document_count'] = sum(item.document_count for item in queryset)
        return context


class BidPackDetailView(DetailView):
    model = BidPack
    template_name = 'bid_generator/bidpack_detail.html'

    def get_queryset(self):
        return filter_queryset_for_user(super().get_queryset(), self.request.user, 'company__organization')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['checklist'] = build_bid_checklist(self.object)
        context['readiness'] = company_readiness(self.object.company)
        context['submission_gaps'] = submission_gap_rows(self.object)
        context['submission_gap_items'] = submission_gap_items(self.object)
        context['xml_document_gaps'] = document_gap_rows_for_company(self.object.tender, self.object.company)
        context['ordered_itb_rows'] = ordered_itb_rows(self.object)
        context['xml_bid_structure_groups'] = xml_bid_structure_groups(self.object)
        context['ordered_attachments'] = ordered_certificate_documents(self.object)
        context['bid_documents'] = self.object.bid_documents.order_by('order')
        context['regeneration_status'] = regeneration_status(self.object)
        match = TenderMatch.objects.filter(tender=self.object.tender, company=self.object.company).first()
        context['decision'] = tender_decision(match, self.object.tender) if match else None
        return context


class BidPackCreateView(CreateView):
    model = BidPack
    form_class = BidPackForm
    template_name = 'bid_generator/bidpack_form.html'

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get('tender'):
            initial['tender'] = self.request.GET['tender']
        if self.request.GET.get('company'):
            initial['company'] = self.request.GET['company']
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tender_id = self.request.GET.get('tender') or self.request.POST.get('tender')
        company_id = self.request.GET.get('company') or self.request.POST.get('company')
        if tender_id and company_id:
            match = TenderMatch.objects.filter(tender_id=tender_id, company_id=company_id).select_related('tender', 'company').first()
            context['decision'] = tender_decision(match, match.tender) if match else None
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Bid pack created. Review readiness, then generate DOCX/PDF.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('bid_generator:detail', args=[self.object.pk])


def generate_bid_pack(request, pk):
    bid_pack = get_object_or_404(filter_queryset_for_user(BidPack.objects.all(), request.user, 'company__organization'), pk=pk)
    save_generated_files(bid_pack)
    messages.success(request, 'Bid pack DOCX and PDF generated.')
    return redirect('bid_generator:detail', pk=pk)


def create_from_tender(request, tender_id):
    tender = get_object_or_404(Tender, pk=tender_id)
    if request.method != 'POST':
        return redirect(tender)
    company = get_object_or_404(filter_queryset_for_user(Company.objects.all(), request.user), pk=request.POST.get('company'))
    bid_pack, created = BidPack.objects.get_or_create(
        tender=tender,
        company=company,
        defaults={
            'include_cover_letter': True,
            'include_checklist': True,
            'include_company_profile': True,
            'include_price_schedule': True,
        },
    )
    if tender.itb_11_items:
        generated = generate_xml_bid_documents(bid_pack)
        messages.success(
            request,
            f'{"Created" if created else "Updated"} bid pack and generated {len(generated)} XML bid document(s).',
        )
    else:
        messages.warning(request, 'Bid pack created, but this tender has no XML structure yet. Upload or fetch the Tender Structure XML first.')
    return redirect('bid_generator:detail', pk=bid_pack.pk)


def generate_bid_documents(request, pk):
    bid_pack = get_object_or_404(filter_queryset_for_user(BidPack.objects.all(), request.user, 'company__organization'), pk=pk)
    generated = generate_xml_bid_documents(bid_pack)
    messages.success(request, f'Generated {len(generated)} bid document(s) from the XML structure.')
    return redirect('bid_generator:detail', pk=pk)


def download_bid_document(request, pk, document_id):
    bid_pack = get_object_or_404(filter_queryset_for_user(BidPack.objects.all(), request.user, 'company__organization'), pk=pk)
    bid_document = get_object_or_404(bid_pack.bid_documents, pk=document_id)
    if not bid_document.generated_pdf:
        raise Http404('This bid document has not been generated yet.')
    try:
        return FileResponse(
            bid_document.generated_pdf.open('rb'),
            as_attachment=request.GET.get('inline') != '1',
            filename=bid_document.generated_pdf.name.rsplit('/', 1)[-1],
            content_type='application/pdf',
        )
    except FileNotFoundError as exc:
        raise Http404('Bid document file was not found. Please regenerate bid documents.') from exc


def download_combined_bid_documents(request, pk):
    bid_pack = get_object_or_404(filter_queryset_for_user(BidPack.objects.all(), request.user, 'company__organization'), pk=pk)
    pdf_bytes = generate_combined_bid_documents_pdf(bid_pack)
    if not pdf_bytes:
        raise Http404('No bid documents are available to combine.')
    filename = f'bid-documents-{bid_pack.pk}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    disposition = 'inline' if request.GET.get('inline') == '1' else 'attachment'
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


def download_bid_pack_file(request, pk, file_type):
    bid_pack = get_object_or_404(filter_queryset_for_user(BidPack.objects.all(), request.user, 'company__organization'), pk=pk)
    if file_type == 'docx':
        generated_file = bid_pack.generated_docx
        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif file_type == 'pdf':
        generated_file = bid_pack.generated_pdf
        content_type = 'application/pdf'
    else:
        raise Http404('Unsupported bid pack file type.')

    if not generated_file:
        raise Http404('Bid pack file has not been generated yet.')

    try:
        return FileResponse(
            generated_file.open('rb'),
            as_attachment=request.GET.get('inline') != '1',
            filename=generated_file.name.rsplit('/', 1)[-1],
            content_type=content_type,
        )
    except FileNotFoundError as exc:
        raise Http404('Bid pack file was not found on the server. Please regenerate it.') from exc
 
# Create your views here.
    generate_combined_bid_documents_pdf,
    generate_xml_bid_documents,
