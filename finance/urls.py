# finance/urls.py
from django.urls import path
from . import views_admin

app_name = 'finance'

urlpatterns = [
    # Admin URLs
    path('admin/', views_admin.admin_dashboard, name='admin_dashboard'),
    path('admin/transactions/', views_admin.admin_transaction_list, name='admin_transaction_list'),
    path('admin/transactions/create/', views_admin.admin_transaction_create, name='admin_transaction_create'),
    path('api/calculate-charge/', views_admin.api_calculate_charge, name='api_calculate_charge'),
    path('api/verify-ecocash/', views_admin.api_verify_ecocash, name='api_verify_ecocash'),
    path('admin/transactions/<int:pk>/', views_admin.admin_transaction_detail, name='admin_transaction_detail'),
    path('admin/receipts/<int:pk>/verify/', views_admin.admin_verify_receipt, name='admin_verify_receipt'),
    path('admin/charges/', views_admin.admin_charges_management, name='admin_charges_management'),
    path('admin/charges/<int:pk>/edit/', views_admin.admin_edit_charge, name='admin_edit_charge'),
    path('admin/charges/<int:pk>/toggle/', views_admin.admin_toggle_charge, name='admin_toggle_charge'),
    path('client-verification/', views_admin.client_verification_list, name='client_verification_list'),
    path('client-verification/<int:pk>/', views_admin.client_verification_detail, name='client_verification_detail'),
    path('client-verification/create/', views_admin.client_verification_create, name='client_verification_create'),
    path('client-verification/<int:pk>/verify/', views_admin.client_verification_verify, name='client_verification_verify'),
    path('client-verification/<int:pk>/unverify/', views_admin.client_verification_unverify, name='client_verification_unverify'),
    path('client-verification/<int:pk>/update/', views_admin.client_verification_update, name='client_verification_update'),
    path('client-verification/<int:pk>/delete/', views_admin.client_verification_delete, name='client_verification_delete'),
    path('client-verification/bulk-action/', views_admin.client_verification_bulk_action, name='client_verification_bulk_action'),
    path('api/verify-ecocash/', views_admin.verify_ecocash_api, name='verify_ecocash_api'),
     path('cashout-transactions/', views_admin.cashout_transaction_list, name='cashout_transaction_list'),
    path('cashout-transactions/<int:pk>/complete/', views_admin.cashout_transaction_mark_completed, name='cashout_transaction_mark_completed'),
    path('cashout-transactions/bulk-complete/', views_admin.cashout_transaction_bulk_complete, name='cashout_transaction_bulk_complete'),
    path('api/cashout-transaction/', views_admin.cashout_transaction_api, name='cashout_transaction_api'),
    
]