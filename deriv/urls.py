from django.urls import path
from . import views

urlpatterns = [
    path('verify-email-callback/', views.verify_email_callback, name='verify_email_callback'),
    path('oauth/callback', views.deriv_oauth_callback, name='deriv_oauth_callback'),
    #  path('verify-app-email-callback/', views.verify_app_email_callback, name='verify_app_email_callback'),
    
]
