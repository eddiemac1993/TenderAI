from django.urls import path

from . import views

app_name = 'tenders'

urlpatterns = [
    path('', views.TenderListView.as_view(), name='list'),
    path('new/', views.TenderCreateView.as_view(), name='create'),
    path('requirements/', views.RequirementListView.as_view(), name='requirements'),
    path('requirements/new/', views.RequirementCreateView.as_view(), name='requirement_create'),
    path('upload-files/', views.TenderFileUploadChooserView.as_view(), name='upload_files_choose'),
    path('zppa/scrape-today/', views.scrape_zppa_today, name='zppa_scrape_today'),
    path('zppa/find-by-url/', views.ZppaUrlImportView.as_view(), name='zppa_find_by_url'),
    path('zppa/scrape-logs/', views.ZppaScrapeLogListView.as_view(), name='zppa_scrape_logs'),
    path('<int:pk>/', views.TenderDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.TenderUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.TenderDeleteView.as_view(), name='delete'),
    path('<int:pk>/requirements/', views.RequirementListView.as_view(), name='tender_requirements'),
    path('<int:tender_id>/requirements/new/', views.RequirementCreateView.as_view(), name='tender_requirement_create'),
    path('<int:pk>/match/', views.TenderMatchView.as_view(), name='match'),
    path('<int:pk>/upload-files/', views.TenderFileUploadView.as_view(), name='upload_files'),
    path('<int:pk>/tasks/', views.BidTaskListView.as_view(), name='tasks'),
    path('<int:pk>/tasks/new/', views.BidTaskCreateView.as_view(), name='task_create'),
    path('<int:pk>/tasks/<int:task_id>/status/', views.update_bid_task_status, name='task_status'),
    path('<int:pk>/analyze-placeholder/', views.analyze_tender_placeholder, name='analyze_placeholder'),
    path('<int:pk>/upload-solicitation/', views.upload_solicitation_document, name='upload_solicitation'),
    path('<int:pk>/fetch-zppa-solicitation/', views.fetch_zppa_solicitation_document, name='fetch_zppa_solicitation'),
    path('<int:pk>/fetch-zppa-documents/', views.fetch_zppa_all_public_documents, name='fetch_zppa_documents'),
    path('<int:pk>/xml-structure.pdf', views.download_xml_structure_pdf, name='download_xml_structure_pdf'),
    path('<int:pk>/ask/', views.ask_tender_chatbot, name='ask_chatbot'),
]
