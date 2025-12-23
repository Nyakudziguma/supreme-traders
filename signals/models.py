from django.db import models
from django.utils import timezone
from accounts.models import User
from subscriptions.models import SubscriptionPlans, Subscribers
import random
import string

class Signal(models.Model):
    SIGNAL_TYPES = (
        ('buy', 'BUY'),
        ('sell', 'SELL'),
        ('hold', 'HOLD'),
        ('alert', 'ALERT'),
    )
    
    MARKET_TYPES = (
        ('forex', 'Forex'),
        ('crypto', 'Cryptocurrency'),
        ('indices', 'Indices'),
        ('commodities', 'Commodities'),
        ('stocks', 'Stocks'),
    )
    
    VOLATILITY_LEVELS = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    )
    
    # Signal Identification
    title = models.CharField(max_length=200, help_text="e.g., V100 Index Buy Signal")
    signal_type = models.CharField(max_length=10, choices=SIGNAL_TYPES, default='buy')
    market_type = models.CharField(max_length=20, choices=MARKET_TYPES, default='indices')
    
    # Asset Details
    asset_name = models.CharField(max_length=100, help_text="e.g., Volatility 100 Index")
    asset_pair = models.CharField(max_length=50, help_text="e.g., V100, EUR/USD, BTC/USD")
    
    # Trade Parameters
    entry_price = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True, help_text="Market execution if empty")
    entry_type = models.CharField(max_length=20, choices=[('market', 'Market Execution'), ('limit', 'Limit Order')], default='market')
    
    # Risk Management
    stop_loss = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    take_profit = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    
    # Position Sizing
    lot_size = models.DecimalField(max_digits=8, decimal_places=2, default=1.00, help_text="Standard lot size")
    min_position = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Minimum position size")
    max_position = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Maximum position size")
    
    # Signal Details
    volatility = models.CharField(max_length=10, choices=VOLATILITY_LEVELS, default='medium')
    confidence = models.IntegerField(default=75, help_text="Confidence level from 1-100")
    
    # Analysis & Notes
    analysis = models.TextField(blank=True, help_text="Technical analysis and reasoning")
    risk_note = models.TextField(default="Ensure proper risk management and only take trades that align with your plan.")
    additional_notes = models.TextField(blank=True, help_text="Any additional instructions")
    
    # WhatsApp Template
    whatsapp_template = models.TextField(default="""📈 Supreme Traders – {{asset_name}} {{signal_type}} Signal

Direction:  {{signal_type}} – {{asset_name}}
Entry: {{entry_type}}
{% if entry_price %}Entry Price:  {{entry_price}}{% endif %}
Stop Loss:  {{stop_loss}}
Take Profit:  {{take_profit}}
Lot Size:  {{lot_size}}
Number of Positions:  Optional — based on your risk appetite

Note: {{risk_note}}
{% if additional_notes %}{{additional_notes}}{% endif %}""")
    
    # Timing
    valid_until = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Status and Tracking
    status = models.CharField(max_length=20, choices=[
        ('draft', 'Draft'),
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('sent', 'Sent'),
        ('expired', 'Expired'),
    ], default='draft')
    
    signal_id = models.CharField(max_length=20, unique=True, editable=False)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_signals')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Trading Signal"
        verbose_name_plural = "Trading Signals"
    
    def __str__(self):
        return f"{self.signal_id} - {self.asset_name} - {self.get_signal_type_display()}"
    
    def get_formatted_message(self):
        """Format the WhatsApp template with actual values"""
        from django.template import Context, Template
        
        template = Template(self.whatsapp_template)
        context = Context({
            'asset_name': self.asset_name,
            'asset_pair': self.asset_pair,
            'signal_type': self.get_signal_type_display(),
            'entry_type': self.get_entry_type_display(),
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'lot_size': self.lot_size,
            'volatility': self.get_volatility_display(),
            'confidence': f"{self.confidence}%",
            'risk_note': self.risk_note,
            'additional_notes': self.additional_notes,
        })
        
        return template.render(context)


class SignalRecipient(models.Model):
    """Track which subscribers received which signals"""
    signal = models.ForeignKey(Signal, on_delete=models.CASCADE, related_name='recipients')
    subscriber = models.ForeignKey(Subscribers, on_delete=models.CASCADE, related_name='received_signals')
    phone_number = models.CharField(max_length=20)
    whatsapp_id = models.CharField(max_length=255, blank=True)
    
    # Delivery Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    ], default='pending')
    
    whatsapp_message_id = models.CharField(max_length=255, blank=True, null=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['signal', 'subscriber']
        verbose_name = "Signal Recipient"
        verbose_name_plural = "Signal Recipients"
    
    def __str__(self):
        return f"{self.signal.signal_id} → {self.phone_number}"
    
    @property
    def delivery_time(self):
        if self.sent_at and self.delivered_at:
            return self.delivered_at - self.sent_at
        return None


class WhatsAppTemplate(models.Model):
    """Pre-defined WhatsApp message templates"""
    TEMPLATE_TYPES = (
        ('signal', 'Trading Signal'),
        ('alert', 'Market Alert'),
        ('news', 'Market News'),
        ('educational', 'Educational Content'),
        ('promotional', 'Promotional'),
    )
    
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    
    # Message content
    subject = models.CharField(max_length=200, blank=True)
    message_body = models.TextField(help_text="Message template. Available variables: {{asset}}, {{type}}, {{entry}}, {{stop_loss}}, {{take_profit}}, {{title}}, {{confidence}}, {{risk}}")
    
    # Variables help
    variables_help = models.TextField(blank=True, help_text="Explanation of available variables")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "WhatsApp Template"
        verbose_name_plural = "WhatsApp Templates"
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class BulkSignalJob(models.Model):
    """Track bulk signal sending jobs"""
    signal = models.ForeignKey(Signal, on_delete=models.CASCADE, related_name='bulk_jobs')
    
    # Job Information
    job_id = models.CharField(max_length=50, unique=True, editable=False)
    initiated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bulk_signal_jobs')
    
    # Recipient filtering
    plan_filter = models.ForeignKey(SubscriptionPlans, on_delete=models.SET_NULL, null=True, blank=True)
    send_to_all_active = models.BooleanField(default=False)
    
    # Statistics
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    delivered_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], default='pending')
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # WhatsApp Configuration
    use_template = models.BooleanField(default=True)
    custom_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Bulk Signal Job"
        verbose_name_plural = "Bulk Signal Jobs"
    
    def __str__(self):
        return f"Bulk Job {self.job_id} - {self.signal.signal_id}"
    
    def save(self, *args, **kwargs):
        if not self.job_id:
            self.job_id = f"JOB{''.join(random.choices(string.digits, k=8))}"
        super().save(*args, **kwargs)
    
    @property
    def success_rate(self):
        if self.total_recipients > 0:
            return (self.sent_count / self.total_recipients) * 100
        return 0