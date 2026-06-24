from django.urls import path

from . import views

app_name = 'quotations'

urlpatterns = [
    path('', views.QuotationListView.as_view(), name='quotation_list'),
    path('new/', views.QuotationCreateView.as_view(), name='quotation_create'),
    path('<int:pk>/', views.QuotationDetailView.as_view(), name='quotation_detail'),
    path('<int:pk>/edit/', views.QuotationUpdateView.as_view(), name='quotation_update'),
    path('<int:pk>/delete/', views.QuotationDeleteView.as_view(), name='quotation_delete'),
    path('<int:pk>/pdf/', views.pdf_placeholder, {'doc_type': 'quotation'}, name='quotation_pdf'),
    path('items/new/', views.QuotationItemCreateView.as_view(), name='quotation_item_create'),
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/new/', views.InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/edit/', views.InvoiceUpdateView.as_view(), name='invoice_update'),
    path('invoices/<int:pk>/delete/', views.InvoiceDeleteView.as_view(), name='invoice_delete'),
    path('invoices/<int:pk>/pdf/', views.pdf_placeholder, {'doc_type': 'invoice'}, name='invoice_pdf'),
    path('invoice-items/new/', views.InvoiceItemCreateView.as_view(), name='invoice_item_create'),
]
