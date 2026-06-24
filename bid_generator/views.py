from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView

from .forms import BidPackForm
from .models import BidPack
from .services import build_bid_checklist, save_generated_files


class BidPackListView(ListView):
    model = BidPack
    template_name = 'bid_generator/bidpack_list.html'
    context_object_name = 'bidpacks'


class BidPackDetailView(DetailView):
    model = BidPack
    template_name = 'bid_generator/bidpack_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['checklist'] = build_bid_checklist(self.object)
        return context


class BidPackCreateView(CreateView):
    model = BidPack
    form_class = BidPackForm
    template_name = 'form.html'
    success_url = reverse_lazy('bid_generator:list')

    def form_valid(self, form):
        messages.success(self.request, 'Bid pack created. DOCX/PDF generation is ready for integration.')
        return super().form_valid(form)


def generate_bid_pack(request, pk):
    bid_pack = get_object_or_404(BidPack, pk=pk)
    save_generated_files(bid_pack)
    messages.success(request, 'Bid pack DOCX and PDF generated.')
    return redirect('bid_generator:detail', pk=pk)

# Create your views here.
