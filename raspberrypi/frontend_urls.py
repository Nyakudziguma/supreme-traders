# econet/urls.py
from django.urls import path
from . import frontend_views as views

app_name = 'econet'

urlpatterns = [
    path('dashboard', views.message_dashboard, name='econet_dashboard'),
    path('messages/', views.econet_messages, name='messages'),
    path('calls/', views.econet_calls, name='calls'),
    path('transfer/', views.money_transfer, name='money_transfer'),
    path('transfer/verify-otp/', views.verify_otp, name='verify_otp'),
    path('transfer/success/<str:reference>/', views.transaction_success, name='transaction_success'),
    path('transfer/history/', views.transaction_history, name='transaction_history'),
    path('transfer/resend-otp/', views.resend_otp, name='resend_otp'),
    path('transfer/cancel/', views.cancel_transaction, name='cancel_transaction'),
    
    # API endpoints for messages
    path('api/send-message/', views.api_send_message, name='api_send_message'),
    path('api/messages/<int:message_id>/delete/', views.api_delete_message, name='api_delete_message'),
    path('api/messages/bulk-action/', views.api_bulk_action, name='api_bulk_action'),
    
    # API endpoints for transactions
    path('api/create-transaction/', views.api_create_transaction, name='api_create_transaction'),
    path('api/send-otp/', views.api_send_otp, name='api_send_otp'),
]