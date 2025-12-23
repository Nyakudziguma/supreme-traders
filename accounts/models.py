# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
import random
import string

class User(AbstractUser):
    USER_TYPES = (
        ('customer', 'Customer'),
        ('trainer', 'Trainer'),
        ('admin', 'Admin'),
    )
    
    REGISTRATION_SOURCES = (
        ('whatsapp', 'WhatsApp Bot'),
        ('web', 'Web Registration'),
        ('admin', 'Admin Created'),
    )
    
    # Make email unique and required
    email = models.EmailField(unique=True)
    
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='customer')
    phone_number = models.CharField(max_length=20, unique=True, help_text="WhatsApp number used for registration")
    date_of_birth = models.DateField(null=True, blank=True)
    registration_source = models.CharField(max_length=20, choices=REGISTRATION_SOURCES, default='whatsapp')
    whatsapp_id = models.CharField(max_length=255, blank=True, help_text="WhatsApp user ID from the bot")
    
    # Blocking fields
    is_blocked = models.BooleanField(default=False)
    blocked_at = models.DateTimeField(null=True, blank=True)
    block_reason = models.TextField(blank=True, help_text="Reason for blocking the user")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    two_factor_enabled = models.BooleanField(default=False)
    totp_secret = models.CharField(max_length=32, blank=True, null=True)
    
    # Use email as the username field
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'phone_number']
    
    def __str__(self):
        return f"{self.email} - {self.phone_number}"

    def save(self, *args, **kwargs):
        # Auto-generate username from email if not provided
        if not self.username:
            self.username = self.email.split('@')[0]
        
        # Auto-generate a random password for WhatsApp users
        if not self.password and self.registration_source == 'whatsapp':
            self.set_password(self.generate_temp_password())
            
        super().save(*args, **kwargs)
    
    def generate_temp_password(self):
        """Generate temporary password for WhatsApp users"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    def block_user(self, reason=""):
        """Block a user and set block details"""
        self.is_blocked = True
        self.blocked_at = models.DateTimeField(auto_now=True)
        self.block_reason = reason
        self.save()
    
    def unblock_user(self):
        """Unblock a user"""
        self.is_blocked = False
        self.block_reason = ""
        self.save()