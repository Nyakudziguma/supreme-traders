from django.contrib import admin
from .models import  CashInTransaction, CashOutTransaction

admin.site.register(CashInTransaction)
admin.site.register(CashOutTransaction)