from django.urls import path
from .switch_views import switch_list, switch_toggle, switch_edit, switch_delete, switch_bulk_toggle, switch_check_status

app_name = 'switches'

urlpatterns = [
    path('', switch_list, name='switch_list'),
    path('toggle/<int:pk>/', switch_toggle, name='switch_toggle'),
    path('edit/', switch_edit, name='switch_create'),
    path('edit/<int:pk>/', switch_edit, name='switch_edit'),
    path('delete/<int:pk>/', switch_delete, name='switch_delete'),
    path('bulk-toggle/', switch_bulk_toggle, name='switch_bulk_toggle'),
    path('api/check/<str:switch_type>/', switch_check_status, name='switch_check_status'),
]