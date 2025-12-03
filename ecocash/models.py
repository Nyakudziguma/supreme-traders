from django.db import models
from accounts.models import User
import random
import string

class CashOutTransaction(models.Model):
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    txn_id = models.CharField(max_length=500, unique=True)
    body = models.TextField()
    completed = models.BooleanField(default=False)
    trader = models.ForeignKey(User,on_delete=models.CASCADE,related_name='cashout_user',null=True,blank=True)
    verification_code = models.CharField(max_length=10,null=True,blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    prev_bal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    new_bal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    flagged = models.BooleanField(default=False)
    fradulent = models.BooleanField(default=False)
    low_limit = models.BooleanField(default=False)

    flag_reason = models.TextField(blank=True, null=True)
    flagged_by = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.pk and not self.verification_code:
            self.verification_code = ''.join(random.choices(string.digits, k=6))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.txn_id} - {self.amount}"


class CashInTransaction(models.Model):
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    name = models.CharField(max_length=100)
    txn_id = models.CharField(max_length=500, unique=True)
    body = models.TextField()
    new_bal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"{self.txn_id} - {self.amount}"