from django.db import models

class AuthDetails(models.Model):
    account_number = models.CharField(max_length=20)
    token = models.CharField(max_length=2555)
    affiliate_token = models.CharField(max_length=255)

    def __str__(self):
        return self.account_number