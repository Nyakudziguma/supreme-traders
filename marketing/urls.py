# marketing/urls.py
from django.urls import path
from . import views

app_name = 'marketing'

urlpatterns = [
    path('', views.marketing_dashboard, name='dashboard'),
    path('campaigns/', views.marketing_campaign_list, name='campaign_list'),
    path('campaigns/create/', views.marketing_campaign_create, name='campaign_create'),
    path('campaigns/<int:pk>/', views.marketing_campaign_detail, name='campaign_detail'),
    path('campaigns/<int:pk>/edit/', views.marketing_campaign_edit, name='campaign_edit'),
    path('campaigns/<int:pk>/send/', views.marketing_campaign_send, name='campaign_send'),
    path('campaigns/<int:pk>/delete/', views.marketing_campaign_delete, name='campaign_delete'),
    path('templates/', views.marketing_template_list, name='template_list'),
    path('analytics/', views.marketing_analytics, name='analytics'),
    path('send-transaction-notification/', views.send_transaction_notification, name='send_transaction_notification'),
]