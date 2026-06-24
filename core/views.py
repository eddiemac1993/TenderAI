from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import UpdateView

from .forms import SystemSettingsForm
from .models import SystemSettings


class SystemSettingsView(UpdateView):
    model = SystemSettings
    form_class = SystemSettingsForm
    template_name = 'core/settings.html'

    def get_object(self, queryset=None):
        return SystemSettings.load()

    def form_valid(self, form):
        messages.success(self.request, 'System settings updated.')
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path

# Create your views here.
