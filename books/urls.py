# books/urls.py
from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    path('', views.books_dashboard, name='dashboard'),
    path('list/', views.books_list, name='list'),
    path('browse/', views.books_browse, name='browse'),
    path('create/', views.book_create, name='create'),
    path('update/<int:pk>/', views.book_update, name='update'),
    path('delete/<int:pk>/', views.book_delete, name='delete'),
    path('detail/<int:pk>/', views.book_detail, name='detail'),
    path('download/<int:pk>/', views.book_download, name='download'),
    path('toggle-featured/<int:pk>/', views.book_toggle_featured, name='toggle_featured'),
    path('toggle-paid/<int:pk>/', views.book_toggle_paid, name='toggle_paid'),
]