from django.db import models
from django.utils import timezone
from accounts.models import User
from finance.models import EcoCashTransaction
from whatsapp.models import ClientVerification

# models.py
class Marketing(models.Model):
    MESSAGE_TYPES = [
        ('transaction_success', 'Transaction Success'),
        ('transaction_failed', 'Transaction Failed'),
        ('marketing', 'Marketing Campaign'),
        ('promotional', 'Promotional Offer'),
        ('educational', 'Educational Content'),
        ('system', 'System Notification'),
        ('welcome', 'Welcome Message'),
    ]
    
    AUDIENCE_TYPES = [
        ('all_users', 'All Users'),
        ('active_users', 'Active Users (30 days)'),
        ('new_users', 'New Users (7 days)'),
        ('verified_users', 'Verified Users'),
        ('unverified_users', 'Unverified Users'),
        ('depositors', 'Users with Deposits'),
        ('withdrawers', 'Users with Withdrawals'),
        ('specific', 'Specific Users'),
    ]
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    message_type = models.CharField(max_length=50, choices=MESSAGE_TYPES, default='marketing')
    audience_type = models.CharField(max_length=50, choices=AUDIENCE_TYPES, default='all_users')
    
    # Images and media
    image = models.ImageField(upload_to='marketing/', blank=True, null=True)
    video_url = models.URLField(blank=True, null=True)
    attachment = models.FileField(upload_to='marketing/attachments/', blank=True, null=True)
    
    # Scheduling
    send_immediately = models.BooleanField(default=True)
    scheduled_for = models.DateTimeField(blank=True, null=True)
    
    # Tracking
    total_sent = models.IntegerField(default=0)
    total_delivered = models.IntegerField(default=0)
    total_read = models.IntegerField(default=0)
    total_clicks = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(blank=True, null=True)
    
    # Analytics
    open_rate = models.FloatField(default=0.0)
    click_rate = models.FloatField(default=0.0)
    
    # Meta
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='marketing_campaigns')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    
    @property
    def status(self):
        if self.is_sent:
            return 'sent'
        elif self.scheduled_for and self.scheduled_for > timezone.now():
            return 'scheduled'
        else:
            return 'draft'
    
    def calculate_metrics(self):
        if self.total_sent > 0:
            self.open_rate = (self.total_read / self.total_sent) * 100
            self.click_rate = (self.total_clicks / self.total_sent) * 100
            self.save()
    
    def get_audience_count(self):
        """Calculate number of users in the audience"""
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        if self.audience_type == 'all_users':
            return User.objects.filter(is_active=True).count()
        elif self.audience_type == 'active_users':
            thirty_days_ago = timezone.now() - timedelta(days=30)
            return User.objects.filter(
                is_active=True,
                last_login__gte=thirty_days_ago
            ).count()
        elif self.audience_type == 'new_users':
            seven_days_ago = timezone.now() - timedelta(days=7)
            return User.objects.filter(
                is_active=True,
                date_joined__gte=seven_days_ago
            ).count()
        elif self.audience_type == 'verified_users':
            return ClientVerification.objects.filter(verified=True).count()
        elif self.audience_type == 'unverified_users':
            return ClientVerification.objects.filter(verified=False).count()
        elif self.audience_type == 'depositors':
            return EcoCashTransaction.objects.filter(
                transaction_type='deposit'
            ).values('user').distinct().count()
        elif self.audience_type == 'withdrawers':
            return EcoCashTransaction.objects.filter(
                transaction_type='withdrawal'
            ).values('user').distinct().count()
        return 0