from datetime import timedelta

from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from companies.models import Company
from core.tenancy import filter_queryset_for_user
from tenders.services import company_readiness

from .forms import CompanyDocumentForm
from .models import CompanyDocument


class DocumentListView(ListView):
    model = CompanyDocument
    template_name = 'documents/document_list.html'
    context_object_name = 'documents'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('company', 'company__organization')
        queryset = filter_queryset_for_user(queryset, self.request.user, 'company__organization')
        return self.apply_filters(queryset)

    def apply_filters(self, queryset):
        today = timezone.localdate()
        company = self.request.GET.get('company', '').strip()
        document_type = self.request.GET.get('document_type', '').strip()
        status = self.request.GET.get('status', '').strip()
        query = self.request.GET.get('q', '').strip()

        if company:
            queryset = queryset.filter(company_id=company)
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        if status == 'expired':
            queryset = queryset.filter(expiry_date__lt=today)
        elif status == 'valid':
            queryset = queryset.filter(Q(expiry_date__gte=today) | Q(expiry_date__isnull=True))
        elif status == 'expiring_30':
            queryset = queryset.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30))
        elif status == 'with_expiry':
            queryset = queryset.filter(expiry_date__isnull=False)
        elif status == 'no_expiry':
            queryset = queryset.filter(expiry_date__isnull=True)
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(notes__icontains=query)
                | Q(company__name__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filtered = self.apply_filters(filter_queryset_for_user(CompanyDocument.objects.select_related('company'), self.request.user, 'company__organization'))
        today = timezone.localdate()
        context['company_options'] = filter_queryset_for_user(Company.objects.order_by('name'), self.request.user)
        context['document_type_options'] = CompanyDocument.DocumentType.choices
        context['status_options'] = [
            ('', 'All statuses'),
            ('valid', 'Ready / valid'),
            ('expiring_30', 'Expiring in 30 days'),
            ('expired', 'Expired'),
            ('with_expiry', 'Has expiry date'),
            ('no_expiry', 'No expiry date'),
        ]
        context['selected_company'] = self.request.GET.get('company', '').strip()
        context['selected_document_type'] = self.request.GET.get('document_type', '').strip()
        context['selected_status'] = self.request.GET.get('status', '').strip()
        context['selected_query'] = self.request.GET.get('q', '').strip()
        context['filtered_count'] = filtered.count()
        context['expired_count'] = filtered.filter(expiry_date__lt=today).count()
        context['expiring_count'] = filtered.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30)).count()
        context['ready_count'] = filtered.filter(Q(expiry_date__gte=today) | Q(expiry_date__isnull=True)).count()
        context['company_count'] = filtered.values('company_id').distinct().count()
        return context


class DocumentDetailView(DetailView):
    model = CompanyDocument
    template_name = 'documents/document_detail.html'

    def get_queryset(self):
        return filter_queryset_for_user(super().get_queryset(), self.request.user, 'company__organization')


class DocumentCreateView(CreateView):
    model = CompanyDocument
    form_class = CompanyDocumentForm
    template_name = 'documents/document_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get('company'):
            initial['company'] = self.request.GET['company']
        if self.request.GET.get('document_type'):
            initial['document_type'] = self.request.GET['document_type']
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['next_url'] = self.request.GET.get('next') or self.request.POST.get('next')
        company_id = self.request.GET.get('company') or self.request.POST.get('company')
        document_type = self.request.GET.get('document_type') or self.request.POST.get('document_type')
        if company_id:
            company = filter_queryset_for_user(Company.objects.filter(pk=company_id), self.request.user).first()
            if company:
                context['selected_company'] = company
                context['selected_company_readiness'] = company_readiness(company)
                context['selected_company_documents'] = company.documents.order_by('document_type', '-expiry_date', '-uploaded_at')[:12]
        if company_id and document_type:
            context['existing_documents'] = CompanyDocument.objects.filter(
                company_id=company_id,
                document_type=document_type,
            ).select_related('company').order_by('-expiry_date', '-uploaded_at')[:5]
        return context

    def form_valid(self, form):
        duplicate_exists = CompanyDocument.objects.filter(
            company=form.cleaned_data['company'],
            document_type=form.cleaned_data['document_type'],
        ).exists()
        response = super().form_valid(form)
        if duplicate_exists:
            messages.warning(self.request, 'Document uploaded. This company already had this document type, so please confirm which copy is current.')
        else:
            messages.success(self.request, 'Company document uploaded.')
        return response

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return next_url
        return super().get_success_url()


class DocumentUpdateView(UpdateView):
    model = CompanyDocument
    form_class = CompanyDocumentForm
    template_name = 'documents/document_form.html'

    def get_queryset(self):
        return filter_queryset_for_user(super().get_queryset(), self.request.user, 'company__organization')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class DocumentDeleteView(DeleteView):
    model = CompanyDocument
    template_name = 'confirm_delete.html'
    success_url = reverse_lazy('documents:list')

    def get_queryset(self):
        return filter_queryset_for_user(super().get_queryset(), self.request.user, 'company__organization')

# Create your views here.
