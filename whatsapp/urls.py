
from django.urls import path
from django.contrib import admin
from. import views

urlpatterns = [
    path('webhook', views.WebhookView.as_view(), name='whatsapp-webhook'),
    path('create-deposit-order/', views.create_deposit_order, name='create-deposit-order'),
    path('add-ecocash-pop/', views.add_ecocash_pop, name='add-ecocash-pop'),
]
