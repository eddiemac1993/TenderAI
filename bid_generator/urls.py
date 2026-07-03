from django.urls import path

from . import views

app_name = 'bid_generator'

urlpatterns = [
    path('', views.BidPackListView.as_view(), name='list'),
    path('new/', views.BidPackCreateView.as_view(), name='create'),
    path('from-tender/<int:tender_id>/', views.create_from_tender, name='create_from_tender'),
    path('<int:pk>/', views.BidPackDetailView.as_view(), name='detail'),
    path('<int:pk>/generate/', views.generate_bid_pack, name='generate'),
    path('<int:pk>/generate-documents/', views.generate_bid_documents, name='generate_documents'),
    path('<int:pk>/documents/<int:document_id>/download/', views.download_bid_document, name='download_document'),
    path('<int:pk>/documents/combined/', views.download_combined_bid_documents, name='download_combined_documents'),
    path('<int:pk>/download/<str:file_type>/', views.download_bid_pack_file, name='download'),
]
