from datetime import timedelta

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView, View

from .forms import CouncilPageForm, CouncilPostImportForm
from .models import CouncilPage, CouncilPost, ScrapeRun
from .services import import_public_post_url, scrape_council_pages


class CouncilOpportunityListView(ListView):
    model = CouncilPost
    template_name = 'council_opportunities/post_list.html'
    context_object_name = 'posts'
    paginate_by = 20

    def get_queryset(self):
        queryset = CouncilPost.objects.select_related('council_page')
        query = self.request.GET.get('q', '').strip()
        province = self.request.GET.get('province', '').strip()
        council = self.request.GET.get('council', '').strip()
        category = self.request.GET.get('category', '').strip()
        keyword = self.request.GET.get('keyword', '').strip()
        period = self.request.GET.get('period', '').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()
        today = timezone.localdate()

        if query:
            queryset = queryset.filter(
                Q(post_text__icontains=query)
                | Q(council_page__name__icontains=query)
                | Q(council_page__district__icontains=query)
                | Q(council_page__province__icontains=query)
            )
        if province:
            queryset = queryset.filter(council_page__province=province)
        if council:
            queryset = queryset.filter(council_page_id=council)
        if category:
            queryset = queryset.filter(category=category)
        if keyword:
            queryset = queryset.filter(matched_keywords__icontains=keyword)
        if period == 'this_week':
            week_start = today - timedelta(days=7)
            queryset = queryset.filter(
                Q(date_posted__date__gte=week_start)
                | Q(date_scraped__date__gte=week_start)
            )
        elif period == 'today':
            queryset = queryset.filter(Q(date_posted__date=today) | Q(date_scraped__date=today))
        elif period == 'last_30':
            start = today - timedelta(days=30)
            queryset = queryset.filter(Q(date_posted__date__gte=start) | Q(date_scraped__date__gte=start))
        if date_from:
            queryset = queryset.filter(Q(date_posted__date__gte=date_from) | Q(date_scraped__date__gte=date_from))
        if date_to:
            queryset = queryset.filter(Q(date_posted__date__lte=date_to) | Q(date_scraped__date__lte=date_to))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['provinces'] = (
            CouncilPage.objects.exclude(province='')
            .order_by('province')
            .values_list('province', flat=True)
            .distinct()
        )
        context['councils'] = CouncilPage.objects.filter(is_active=True).order_by('name')
        context['categories'] = CouncilPost.Category.choices
        context['keywords'] = [
            'CDF',
            'Tender',
            'RFQ',
            'Procurement',
            'Grant',
            'Bursary',
            'Youth',
            'Women',
            'Cooperative',
        ]
        context['period_options'] = [
            ('', 'All time'),
            ('today', 'Today'),
            ('this_week', 'This week'),
            ('last_30', 'Last 30 days'),
        ]
        context['coverage'] = {
            'total_councils': CouncilPage.objects.count(),
            'councils_with_urls': CouncilPage.objects.exclude(facebook_url='').count(),
            'councils_missing_urls': CouncilPage.objects.filter(facebook_url='').count(),
            'captured_posts': CouncilPost.objects.count(),
        }
        context['latest_run'] = ScrapeRun.objects.first()
        context['page_form'] = CouncilPageForm(initial={'is_active': True})
        context['filters'] = {
            'q': self.request.GET.get('q', '').strip(),
            'province': self.request.GET.get('province', '').strip(),
            'council': self.request.GET.get('council', '').strip(),
            'category': self.request.GET.get('category', '').strip(),
            'keyword': self.request.GET.get('keyword', '').strip(),
            'period': self.request.GET.get('period', '').strip(),
            'date_from': self.request.GET.get('date_from', '').strip(),
            'date_to': self.request.GET.get('date_to', '').strip(),
        }
        return context


class CouncilPageCreateView(CreateView):
    model = CouncilPage
    form_class = CouncilPageForm
    template_name = 'council_opportunities/page_form.html'
    success_url = reverse_lazy('council_opportunities:list')

    def form_valid(self, form):
        messages.success(self.request, 'Council Facebook page saved. You can scrape it now.')
        return super().form_valid(form)


class CouncilPageListView(ListView):
    model = CouncilPage
    template_name = 'council_opportunities/page_list.html'
    context_object_name = 'council_pages'
    paginate_by = 30

    def get_queryset(self):
        queryset = CouncilPage.objects.all()
        query = self.request.GET.get('q', '').strip()
        province = self.request.GET.get('province', '').strip()
        status = self.request.GET.get('status', '').strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(district__icontains=query)
                | Q(province__icontains=query)
                | Q(facebook_url__icontains=query)
            )
        if province:
            queryset = queryset.filter(province=province)
        if status == 'missing_url':
            queryset = queryset.filter(facebook_url='')
        elif status == 'with_url':
            queryset = queryset.exclude(facebook_url='')
        return queryset.order_by('province', 'district', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['provinces'] = (
            CouncilPage.objects.exclude(province='')
            .order_by('province')
            .values_list('province', flat=True)
            .distinct()
        )
        context['filters'] = {
            'q': self.request.GET.get('q', '').strip(),
            'province': self.request.GET.get('province', '').strip(),
            'status': self.request.GET.get('status', '').strip(),
        }
        context['total_count'] = self.get_queryset().count()
        return context


class CouncilPageUpdateView(UpdateView):
    model = CouncilPage
    form_class = CouncilPageForm
    template_name = 'council_opportunities/page_form.html'
    success_url = reverse_lazy('council_opportunities:page_list')

    def form_valid(self, form):
        messages.success(self.request, 'Council source updated.')
        return super().form_valid(form)


class CouncilScrapeNowView(View):
    def post(self, request):
        run = scrape_council_pages()
        if run.status == ScrapeRun.Status.SUCCESS:
            messages.success(
                request,
                f'Scrape complete: {run.posts_created} new post(s), {run.posts_updated} updated.',
            )
        elif run.status == ScrapeRun.Status.PARTIAL:
            messages.warning(request, f'Scrape partly completed: {run.message}')
        else:
            messages.error(request, f'Scrape failed: {run.message or "No public posts could be read."}')
        return redirect('council_opportunities:list')


class CouncilPostImportView(View):
    template_name = 'council_opportunities/post_import.html'

    def get(self, request):
        from django.shortcuts import render

        return render(request, self.template_name, {'form': CouncilPostImportForm()})

    def post(self, request):
        from django.shortcuts import render

        form = CouncilPostImportForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        try:
            created, post, keywords = import_public_post_url(
                form.cleaned_data['council_page'],
                form.cleaned_data['post_url'],
                form.cleaned_data.get('post_text', ''),
            )
        except Exception as exc:
            messages.error(request, f'Could not import that public post: {exc}')
            return render(request, self.template_name, {'form': form})

        if not post:
            messages.warning(request, 'The post was public but did not match the current opportunity keywords.')
            return render(request, self.template_name, {'form': form})

        action = 'Imported' if created else 'Updated'
        messages.success(request, f'{action} council post. Matched: {", ".join(keywords)}.')
        return redirect('council_opportunities:list')
