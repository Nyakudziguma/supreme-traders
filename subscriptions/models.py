from django.db import models
from accounts.models import User

class SubscriptionPlans(models.Model):
    plan_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    duration_days = models.IntegerField()

    def __str__(self):
        return self.plan_name

class Subscribers(models.Model):
    trader = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlans, on_delete=models.CASCADE)
    ecocash_number = models.CharField(max_length=15, blank=True, null=True)
    pop_image = models.ImageField(upload_to='pop/', blank=True, null=True)
    subscribed_on = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    expiry_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return str(self.trader.username) + " - " + str(self.plan.plan_name)