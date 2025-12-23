# signals/urls.py
from django.urls import path
from . import views

app_name = 'signals'

urlpatterns = [
    # Dashboard
    path('', views.signal_dashboard, name='dashboard'),
    
    # Signals CRUD
    path('signals/', views.signal_list, name='signal_list'),
    path('signals/create/', views.create_signal, name='create_signal'),
    path('signals/<int:pk>/', views.signal_detail, name='signal_detail'),
    path('signals/<int:pk>/edit/', views.edit_signal, name='edit_signal'),
    path('signals/<int:pk>/send-test/', views.send_test_signal, name='send_test_signal'),
    
    # Bulk Sending
    path('signals/<int:pk>/send-bulk/', views.send_bulk_signal, name='send_bulk_signal'),
    path('bulk-jobs/', views.bulk_jobs_list, name='bulk_jobs_list'),
    path('bulk-jobs/<int:pk>/', views.bulk_job_detail, name='bulk_job_detail'),
    
    # WhatsApp Templates
    path('whatsapp-templates/', views.whatsapp_templates, name='whatsapp_templates'),
    
    # Subscriber Management
    path('subscribers/', views.subscriber_management, name='subscriber_management'),
    path('subscribers/<int:pk>/toggle-status/', views.toggle_subscriber_status, name='toggle_subscriber_status'),
]