from django.urls import path
from . import views
from .views import receive_message, receive_incoming_call, log_outgoing_message, get_messages
from . import frontend_views as econet_views

urlpatterns = [
    path('api/receive-message/', receive_message, name='receive-message'),
    path('api/incoming-call/', receive_incoming_call, name='incoming-call'),
    path('api/outgoing-message/', log_outgoing_message, name='outgoing-message'),
    path("api/messages/", get_messages, name="get_messages"),
]