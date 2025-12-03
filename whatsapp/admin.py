from django.contrib import admin
from .models import WhatsAppSession, WhatsAppMessage, InitiateOrders, EcocashPop

# Register your models here.
admin.site.register(WhatsAppSession)
admin.site.register(WhatsAppMessage)
admin.site.register(InitiateOrders)
admin.site.register(EcocashPop)