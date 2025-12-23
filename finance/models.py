# finance/models.py
from django.db import models
from django.utils.timezone import now
from django.contrib.auth import get_user_model
import random
import string
from decimal import Decimal
from datetime import timedelta
User = get_user_model()
from django.core.exceptions import ValidationError


class BillingCycle(models.Model):
    TRANSACTION_DEPOSIT = "deposit"
    TRANSACTION_WITHDRAWAL = "withdrawal"

    TRANSACTION_TYPES = (
        (TRANSACTION_DEPOSIT, "Deposit"),
        (TRANSACTION_WITHDRAWAL, "Withdrawal"),
    )

    client_name = models.CharField(max_length=255)
    start_date = models.DateField(default=now)
    end_date = models.DateField(null=True, blank=True)

    deposit_fee_rate = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal("0.0075")
    )  # 0.5%

    withdrawal_fee_rate = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal("0.01")
    )  # 1%

    transactions_count = models.PositiveIntegerField(default=0)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    paid = models.BooleanField(default=False)

    def add_transaction(self, amount, transaction_type):
        """
        Add a completed transaction to billing
        Fee = amount × fee_rate (based on transaction type)
        """
        amount = Decimal(amount)

        if transaction_type == self.TRANSACTION_DEPOSIT:
            fee = amount * self.deposit_fee_rate

        elif transaction_type == self.TRANSACTION_WITHDRAWAL:
            fee = amount * self.withdrawal_fee_rate

        else:
            raise ValueError("Invalid transaction type")

        self.transactions_count += 1
        self.amount_due += fee
        self.save()

    def close_cycle(self):
        """Mark this cycle as paid and start a new billing cycle"""
        self.paid = True
        self.save()

        return BillingCycle.objects.create(
            client_name=self.client_name,
            start_date=now().date(),
            end_date=(now() + timedelta(days=30)).date(),
            deposit_fee_rate=self.deposit_fee_rate,
            withdrawal_fee_rate=self.withdrawal_fee_rate,
        )


class TransactionCharge(models.Model):
    """Fixed charges table based on amount ranges"""
    min_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Minimum amount for this fee range (inclusive)"
    )
    max_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Maximum amount for this fee range (inclusive)"
    )
    fixed_charge = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Fixed charge amount in USD"
    )
    is_percentage = models.BooleanField(
        default=False,
        help_text="Whether this uses percentage calculation ($10+ range)"
    )
    percentage_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=0.00,
        help_text="Percentage rate (only for $10+ range)"
    )
    additional_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0.00,
        help_text="Additional fixed fee (only for $10+ range)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Transaction Charge"
        verbose_name_plural = "Transaction Charges"
        ordering = ['min_amount']
        constraints = [
            models.CheckConstraint(
                check=models.Q(min_amount__lte=models.F('max_amount')),
                name='min_amount_lte_max_amount'
            )
        ]
    
    def __str__(self):
        if self.is_percentage:
            return f"${self.min_amount}+: {self.percentage_rate}% + ${self.additional_fee}"
        else:
            return f"${self.min_amount}-${self.max_amount}: ${self.fixed_charge}"
    
    def calculate_charge(self, amount):
        """Calculate charge for given amount"""
        if self.is_percentage:
            # For $10+ range: 10% + 90 cents
            return (amount * self.percentage_rate / Decimal('100')) + self.additional_fee
        else:
            # For fixed fee ranges
            return self.fixed_charge
    
    @classmethod
    def get_charge_for_amount(cls, amount):
        """Get the appropriate charge for a given amount"""
        try:
            # First check for percentage-based range ($10+)
            percentage_charge = cls.objects.filter(
                min_amount__lte=amount,
                max_amount__gte=amount,
                is_percentage=True,
                is_active=True
            ).first()
            
            if percentage_charge:
                return percentage_charge.calculate_charge(amount)
            
            # Check for fixed fee ranges
            fixed_charge = cls.objects.filter(
                min_amount__lte=amount,
                max_amount__gte=amount,
                is_percentage=False,
                is_active=True
            ).first()
            
            if fixed_charge:
                return fixed_charge.calculate_charge(amount)
            
            # If no specific range found, use the highest percentage range
            highest_percentage = cls.objects.filter(
                is_percentage=True,
                is_active=True
            ).order_by('-min_amount').first()
            
            if highest_percentage:
                return highest_percentage.calculate_charge(amount)
                
        except Exception:
            pass
        
        # Default fallback
        return Decimal('0.00')


class EcoCashTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('deposit', 'Deposit to Deriv'),
        ('withdrawal', 'Withdrawal from Deriv'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('awaiting_pop', 'Awaiting POP'), 
    )
    
    # User and transaction info
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ecocash_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    
    # Core transaction fields
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    deriv_account_number = models.CharField(
        max_length=50,
        help_text="Your Deriv account number / CR number",
        verbose_name="Deriv Account/CR Number"
    )
    ecocash_number = models.CharField(
        max_length=50,
        help_text="Your EcoCash phone number"
    )
    ecocash_name = models.CharField(
        max_length=100,
        help_text="Name registered with your EcoCash"
    )
    charge = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Transaction fee")
    
    # Status and timing
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=now)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Reference number (auto-generated)
    reference_number = models.CharField(max_length=20, unique=True, editable=False)
    
    # EcoCash reference from POP (for deposits)
    ecocash_reference = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="EcoCash reference number from POP",
        verbose_name="EcoCash Reference"
    )
    
    # Deriv transaction tracking (for deposits)
    deriv_transaction_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Deriv's transaction reference after deposit"
    )
    
    # EcoCash transaction ID (for withdrawals)
    ecocash_transaction_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="EcoCash transaction ID for withdrawals"
    )
    
    # Additional fields
    currency = models.CharField(max_length=10, default='USD')
    description = models.TextField(blank=True, help_text="Transaction description")
    admin_notes = models.TextField(blank=True, help_text="Internal admin notes")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "EcoCash Transaction"
        verbose_name_plural = "EcoCash Transactions"
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['reference_number']),
            models.Index(fields=['ecocash_reference']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type.upper()} - {self.amount} {self.currency} - {self.reference_number} - {self.status}"
    

    # -----------------------------
    # ECOCASH NUMBER NORMALISATION
    # -----------------------------
    def clean_ecocash(self):
        """Normalise EcoCash number into 9-digit format starting with 7."""
        number = (self.ecocash_number or "").strip()

        # Remove spaces + plus sign
        number = number.replace(" ", "").replace("+", "")

        # Accept "2637" or "26378" formats
        if number.startswith("263"):
            number = number[3:]

        # Accept "07..." → convert to "7..."
        if number.startswith("07"):
            number = number[1:]

        # Final validation
        if not (number.isdigit() and len(number) == 9 and number.startswith("7")):
            raise ValidationError("Invalid EcoCash number format")

        return number


    def save(self, *args, **kwargs):
        # Always normalise EcoCash number
        if self.ecocash_number:
            self.ecocash_number = self.clean_ecocash()

        # Generate reference number if missing
        if not self.reference_number:
            self.reference_number = self.generate_reference_number()
        
        # Charge logic
        if self.transaction_type == 'withdrawal':
            self.charge = 0
        elif self.charge == 0 and self.amount > 0 and self.transaction_type == 'deposit':
            self.charge = TransactionCharge.get_charge_for_amount(self.amount)
        
        # Status logic
        if self.transaction_type == 'deposit' and self.status == 'pending':
            self.status = 'awaiting_pop'
            
        if self.status == 'completed' and not self.processed_at:
            self.processed_at = now()
        
        # Check new completion
        is_new_completion = False
        if self.pk and EcoCashTransaction.objects.filter(pk=self.pk).exists():
            original = EcoCashTransaction.objects.get(pk=self.pk)
            if original.status != "completed" and self.status == "completed":
                is_new_completion = True
        else:
            if self.status == "completed":
                is_new_completion = True
            
        super().save(*args, **kwargs)

        # Billing cycle integration (deposit + withdrawal)
        if is_new_completion and self.transaction_type in ["deposit", "withdrawal"]:
            billing, created = BillingCycle.objects.get_or_create(
                client_name="Supreme AI",
                paid=False,
                defaults={
                    "start_date": now().date(),
                    "end_date": now().date() + timedelta(days=30),
                }
            )

            billing.add_transaction(
                amount=self.amount,
                transaction_type=self.transaction_type
            )

    

    # ------------------------------------
    # REFERENCE NUMBER GENERATOR (UNCHANGED)
    # ------------------------------------
    def generate_reference_number(self):
        """Generate unique 9-character reference number: 3 letters + 6 digits."""
        while True:
            letters = ''.join(random.choices(string.ascii_uppercase, k=3))
            numbers = ''.join(random.choices(string.digits, k=6))
            ref_number = f"{letters}{numbers}"
            
            if not EcoCashTransaction.objects.filter(reference_number=ref_number).exists():
                return ref_number
    

    # --------------------
    # CALCULATED PROPERTIES
    # --------------------
    @property
    def total_amount(self):
        if self.transaction_type == 'deposit':
            return self.amount + self.charge
        return self.amount
    
    @property
    def is_successful(self):
        return self.status == 'completed'
    
    @property
    def requires_pop(self):
        return self.transaction_type == 'deposit' and self.status == 'awaiting_pop'
    
    @property
    def can_be_cancelled(self):
        return self.status in ['pending', 'awaiting_pop', 'processing']
    

    # -------------------------
    # ACTION METHODS (UNCHANGED)
    # -------------------------
    def submit_pop(self, ecocash_reference, receipt_image=None):
        if self.transaction_type != 'deposit':
            raise ValueError("Only deposit transactions require POP")
        
        self.ecocash_reference = ecocash_reference
        self.status = 'processing'
        self.save()
        
        if receipt_image:
            TransactionReceipt.objects.create(
                transaction=self,
                receipt_image=receipt_image,
                uploaded_by=self.user
            )
    
    def mark_deposit_completed(self, deriv_transaction_id, notes=""):
        if self.transaction_type != 'deposit':
            raise ValueError("This method is for deposit transactions only")
        
        self.status = 'completed'
        self.deriv_transaction_id = deriv_transaction_id
        self.processed_at = now()
        if notes:
            self.admin_notes = notes
        self.save()
    
    def mark_withdrawal_completed(self, ecocash_transaction_id, notes=""):
        if self.transaction_type != 'withdrawal':
            raise ValueError("This method is for withdrawal transactions only")
        
        self.status = 'completed'
        self.ecocash_transaction_id = ecocash_transaction_id
        self.processed_at = now()
        if notes:
            self.admin_notes = notes
        self.save()
    
    def mark_failed(self, reason=""):
        self.status = 'failed'
        if reason:
            self.admin_notes = reason
        self.save()

class TransactionReceipt(models.Model):
    """Store transaction receipts and proof of payment"""
    transaction = models.OneToOneField(EcoCashTransaction, on_delete=models.CASCADE, related_name='receipt')
    receipt_image = models.ImageField(
        upload_to='receipts/%Y/%m/%d/', 
        blank=True, 
        null=True,
        help_text="Screenshot of EcoCash POP"
    )
    receipt_number = models.CharField(max_length=100, blank=True, help_text="EcoCash receipt number")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_receipts')
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True, help_text="Admin verification notes")
    
    def __str__(self):
        return f"Receipt for {self.transaction.reference_number}"
    
    class Meta:
        verbose_name = "Transaction Receipt"
        verbose_name_plural = "Transaction Receipts"

class AuditLog(models.Model):
    trader = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit')
    action = models.CharField(max_length=255)  # Description of the action (e.g., "Funded account", "Withdrew funds")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.trader.username} - {self.action} at {self.timestamp}"

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    transaction = models.ForeignKey(EcoCashTransaction, on_delete=models.CASCADE, related_name='user_notifications')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification to {self.recipient.username}"
