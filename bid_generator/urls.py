from django.urls import path

from . import views

app_name = 'bid_generator'

urlpatterns = [
    path('', views.BidPackListView.as_view(), name='list'),
    path('new/', views.BidPackCreateView.as_view(), name='create'),
    path('<int:pk>/', views.BidPackDetailView.as_view(), name='detail'),
    path('<int:pk>/generate/', views.generate_bid_pack, name='generate'),
]
