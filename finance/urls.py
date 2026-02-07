# finance/urls.py
from django.urls import path
from . import views_admin
from weltrade import views as binance_views


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
    path('client-verification/<int:pk>/reject/', views_admin.client_verification_reject, name='client_verification_reject'),
    path('client-verification/<int:pk>/approve/', views_admin.client_verification_approve, name='client_verification_approve'),
    path('client-verification/<int:pk>/update/', views_admin.client_verification_update, name='client_verification_update'),
    path('api/verify-ecocash/', views_admin.verify_ecocash_api, name='verify_ecocash_api'),
     path('cashout-transactions/', views_admin.cashout_transaction_list, name='cashout_transaction_list'),
    path('cashout-transactions/<int:pk>/complete/', views_admin.cashout_transaction_mark_completed, name='cashout_transaction_mark_completed'),
    path('cashout-transactions/bulk-complete/', views_admin.cashout_transaction_bulk_complete, name='cashout_transaction_bulk_complete'),
    path('api/cashout-transaction/', views_admin.cashout_transaction_api, name='cashout_transaction_api'),
    path('cashout-transactions/create/', views_admin.cashout_transaction_create, name='cashout_transaction_create'),

    path('binance-settings/', binance_views.binance_settings_list, name='binance_settings_list'),
    path('binance-settings/create/', binance_views.binance_settings_create, name='binance_settings_create'),
    path('binance-settings/<int:pk>/update/', binance_views.binance_settings_update, name='binance_settings_update'),
    path('binance-settings/<int:pk>/delete/', binance_views.binance_settings_delete, name='binance_settings_delete'),
    path('binance-settings/<int:pk>/toggle/', binance_views.binance_settings_toggle, name='binance_settings_toggle'),
    path('binance-settings/<int:pk>/test/', binance_views.binance_settings_test, name='binance_settings_test'),
    
]