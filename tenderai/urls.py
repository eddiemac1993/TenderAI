"""
URL configuration for tenderai project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import AppUpdateView, RegisterView, TenderAILoginView, run_app_update

from .views import AboutView, DashboardView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('about/', AboutView.as_view(), name='about'),
    path('admin/', admin.site.urls),
    path('accounts/login/', TenderAILoginView.as_view(), name='login'),
    path('accounts/register/', RegisterView.as_view(), name='register'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('updates/', AppUpdateView.as_view(), name='app_update_direct'),
    path('updates/run/', run_app_update, name='run_app_update_direct'),
    path('settings/', include('core.urls')),
    path('companies/', include('companies.urls')),
    path('documents/', include('documents.urls')),
    path('tenders/', include('tenders.urls')),
    path('bids/', include('bid_generator.urls')),
    path('council-opportunities/', include('council_opportunities.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
