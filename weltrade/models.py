from django.db import models

class BinanceSettings(models.Model):
    api_key = models.TextField()
    api_secret = models.TextField()
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Binance Key {self.id}"