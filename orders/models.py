from django.db import models
import uuid

class Balance(models.Model):
    BALANCE_TYPES = [
        ("main", "main"),
        ("Agent", "Agent"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) 
    name = models.CharField(max_length=50, choices=BALANCE_TYPES) 
    balance = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.get_name_display()} - {self.balance}"

