
from django.urls import path
from django.contrib import admin
from. import views

urlpatterns = [
    path('webhook', views.WebhookView.as_view(), name='whatsapp-webhook'),
    path('create-deposit-order/', views.create_deposit_order, name='create-deposit-order'),
    path('add-ecocash-pop/', views.add_ecocash_pop, name='add-ecocash-pop'),
    path('add-signals-pop/', views.add_signals_pop, name='add-signals-pop'),
    path('create-withdrawal-order/', views.create_withdrawal_order, name='create-withdrawal-order'),
    path('add-ecocash-message-pop/', views.add_ecocash_message_pop, name='add-ecocash-message-pop'),
]
