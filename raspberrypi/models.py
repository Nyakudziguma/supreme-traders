# models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# Your existing models
class IncomingMessage(models.Model):
    sender_id = models.CharField(max_length=20)
    message_body = models.TextField()
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender_id} - {self.received_at}"

class IncomingCall(models.Model):
    caller_id = models.CharField(max_length=20)
    call_time = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.IntegerField()

    def __str__(self):
        return f"Call from {self.caller_id} - {self.duration_seconds}s"

class OutgoingMessage(models.Model):
    recipient_id = models.CharField(max_length=20)
    message_body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"To {self.recipient_id} @ {self.sent_at}"

# EcocashTransfers model
class EcocashTransfers(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Successful", "Successful"), 
        ("Failed", "Failed"),
    ]
    
    TRANSACTION_TYPES = [
        ("Agent", "Agent Transfer"),
        ("User", "User Transfer"),
       
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ecocash_transfers')
    transaction_type = models.CharField(max_length=100, choices=TRANSACTION_TYPES, default="User")
    ecocash_name = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    ecocash_number = models.CharField(max_length=15)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    reference_number = models.CharField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "EcoCash Transfer"
        verbose_name_plural = "EcoCash Transfers"

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.status}"
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            import uuid
            self.reference_number = f"ECO{str(uuid.uuid4())[:8].upper()}"
        super().save(*args, **kwargs)
    
    def mark_as_successful(self):
        self.status = "Successful"
        self.processed_at = timezone.now()
        self.save()
    
    def mark_as_failed(self, reason=""):
        self.status = "Failed"
        self.description = f"{self.description} | Failed: {reason}" if self.description else f"Failed: {reason}"
        self.processed_at = timezone.now()
        self.save()

# OTP model for transaction verification
class TransactionOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transaction_otps')
    otp_code = models.CharField(max_length=6)
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=100)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP for {self.phone_number} - {self.amount}"
    
    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at