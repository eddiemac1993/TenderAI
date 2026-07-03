from django.urls import path

from .views import (
    CouncilOpportunityListView,
    CouncilPageCreateView,
    CouncilPageListView,
    CouncilPageUpdateView,
    CouncilPostImportView,
    CouncilScrapeNowView,
)

app_name = 'council_opportunities'

urlpatterns = [
    path('', CouncilOpportunityListView.as_view(), name='list'),
    path('pages/', CouncilPageListView.as_view(), name='page_list'),
    path('pages/new/', CouncilPageCreateView.as_view(), name='page_create'),
    path('pages/<int:pk>/edit/', CouncilPageUpdateView.as_view(), name='page_update'),
    path('posts/import/', CouncilPostImportView.as_view(), name='post_import'),
    path('scrape-now/', CouncilScrapeNowView.as_view(), name='scrape_now'),
]
