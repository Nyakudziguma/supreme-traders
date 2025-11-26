# finance/urls.py
from django.urls import path
from . import views_admin

app_name = 'finance'

urlpatterns = [
    # Admin URLs
    path('admin/', views_admin.admin_dashboard, name='admin_dashboard'),
    path('admin/transactions/', views_admin.admin_transaction_list, name='admin_transaction_list'),
    path('admin/transactions/create/', views_admin.admin_transaction_create, name='admin_transaction_create'),
    path('admin/transactions/<int:pk>/', views_admin.admin_transaction_detail, name='admin_transaction_detail'),
    path('admin/receipts/<int:pk>/verify/', views_admin.admin_verify_receipt, name='admin_verify_receipt'),
    path('admin/charges/', views_admin.admin_charges_management, name='admin_charges_management'),
    path('admin/charges/<int:pk>/edit/', views_admin.admin_edit_charge, name='admin_edit_charge'),
    path('admin/charges/<int:pk>/toggle/', views_admin.admin_toggle_charge, name='admin_toggle_charge'),
    
]