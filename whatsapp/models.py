# whatsapp/models.py
from decimal import Decimal
from django.db import models
from accounts.models import User

class WhatsAppSession(models.Model):
    """Track WhatsApp bot sessions and user interactions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='whatsapp_sessions')
    phone_number = models.CharField(max_length=20)
    session_id = models.CharField(max_length=255, unique=True)
    previous_step = models.CharField(max_length=100, blank=True, null=True)
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

class InitiateOrders(models.Model):
     ORDER_TYPES = (
        ('deposit', 'Deriv Deposit'),
        ('weltrade_deposit', 'Weltrade Deposit'),
     )
     trader = models.ForeignKey(User, on_delete=models.CASCADE)
     amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
     ecocash_number = models.CharField(max_length=15)
     txn_Id = models.CharField(max_length=100, blank=True, null=True)
     account_number = models.CharField(max_length=100)
     order_type = models.CharField(max_length=50, choices=ORDER_TYPES, default='deposit')

     def __str__(self):
            return self.account_number

class InitiateSellOrders(models.Model):
     trader = models.ForeignKey(User, on_delete=models.CASCADE)
     amount = models.DecimalField(max_digits=12, decimal_places=2)
     ecocash_number = models.CharField(max_length=15, blank=True, null=True)
     ecocash_name = models.CharField(max_length=100, blank=True, null=True)
     account_number = models.CharField(max_length=50)
     email = models.EmailField()

     def __str__(self):
            return self.account_number
     
class EcocashPop(models.Model):
    order = models.ForeignKey(InitiateOrders, on_delete=models.CASCADE, related_name='ecocash_pops')
    ecocash_pop = models.ImageField(upload_to='ecocash_pops/', blank=True, null=True)
    ecocash_message = models.TextField(blank=True, null=True)
    has_image = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"Ecocash POP for Order {self.order.id}"


from django.core.exceptions import ValidationError

class ClientVerification(models.Model):
    trader = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    ecocash_number = models.CharField(max_length=20, unique=True)

    national_id_image = models.ImageField(upload_to='clients/ids/', blank=True, null=True)
    selfie_with_id = models.ImageField(upload_to='clients/selfies/', blank=True, null=True)
    crypto_wallet_address = models.CharField(max_length=255, blank=True, null=True)
    rejected = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'is_staff': True},
        related_name='verified_clients'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean_ecocash(self):
        number = self.ecocash_number.strip()

        # remove spaces and +
        number = number.replace(" ", "").replace("+", "")

        # If starts with 263
        if number.startswith("263"):
            number = number[3:]   # remove 263 → "786976684"

        # If starts with 07
        if number.startswith("07"):
            number = number[1:]   # remove "0" → "786976684"

        # Final validation: must start with 7 and be 9 digits
        if not (number.startswith("7") and number.isdigit() and len(number) == 9):
            raise ValidationError("Invalid EcoCash number format")

        return number

    def save(self, *args, **kwargs):
        self.ecocash_number = self.clean_ecocash()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.ecocash_number})"

    @property
    def status(self):
        return "Verified" if self.verified else "Unverified"


class EcocashAgent(models.Model):
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, unique=True)
    balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.phone_number})"

    def credit(self, amount):
        """Add amount to the agent's balance."""
        self.balance += Decimal(amount)
        self.save()

    def debit(self, amount):
        """Subtract amount from the agent's balance."""
        if Decimal(amount) > self.balance:
            raise ValueError("Insufficient balance")
        self.balance -= Decimal(amount)
        self.save()

class BlacklistedNumber(models.Model):
    number = models.CharField(max_length=20, unique=True)
    reason = models.TextField(blank=True, null=True)     
    created_at = models.DateTimeField(auto_now_add=True) 

    def __str__(self):
        return self.number

class Switch(models.Model):
    Transaction_Types = (
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('signals', 'Signals'),
        ('books', 'Books'),
        ('training', 'Training'),
        ('weltrade_deposit', 'Weltrade Deposit'),
        ('other', 'Other'),
    )
    transaction_type = models.CharField(max_length=50, choices=Transaction_Types)
    off_message = models.TextField(blank=True, null=True)
    on_message = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_type} - {'Active' if self.is_active else 'Inactive'}"


    