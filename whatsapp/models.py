# whatsapp/models.py
from django.db import models
from accounts.models import User

class WhatsAppSession(models.Model):
    """Track WhatsApp bot sessions and user interactions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='whatsapp_sessions')
    phone_number = models.CharField(max_length=20)
    session_id = models.CharField(max_length=255, unique=True)
    current_step = models.CharField(max_length=100, default='welcome')
    conversation_data = models.JSONField(default=dict, help_text="Store temporary conversation data")
    is_active = models.BooleanField(default=True)
    last_interaction = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-last_interaction']
    
    def __str__(self):
        return f"{self.phone_number} - {self.current_step}"

class WhatsAppMessage(models.Model):
    """Log all WhatsApp messages for analytics and debugging"""
    MESSAGE_TYPES = (
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    )
    
    session = models.ForeignKey(WhatsAppSession, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    message_body = models.TextField()
    message_from = models.CharField(max_length=20)
    message_to = models.CharField(max_length=20)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='sent', choices=(
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    ))
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.message_type} - {self.message_from} - {self.timestamp}"