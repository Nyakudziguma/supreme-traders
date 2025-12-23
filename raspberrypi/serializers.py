from rest_framework import serializers
from .models import IncomingMessage, IncomingCall, OutgoingMessage


class IncomingCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomingCall
        fields = ['id', 'caller_id', 'duration_seconds', 'call_time']


class OutgoingMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutgoingMessage
        fields = ['id', 'recipient_id', 'message_body', 'sent_at']

# raspberrypi/serializers.py
from rest_framework import serializers
from .models import IncomingMessage

class IncomingMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomingMessage
        fields = ['id', 'sender_id', 'message_body', 'received_at']
