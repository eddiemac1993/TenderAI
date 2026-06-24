from django.urls import path

from .views import SystemSettingsView

app_name = 'core'

urlpatterns = [
    path('', SystemSettingsView.as_view(), name='settings'),
]
