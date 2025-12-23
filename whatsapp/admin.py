from django.contrib import admin
from .models import WhatsAppSession, WhatsAppMessage, InitiateOrders, EcocashPop, Switch, InitiateSellOrders

# Register your models here.
admin.site.register(InitiateOrders)
admin.site.register(EcocashPop)

class WhatsAppSessionAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'user', 'current_step', 'last_interaction', 'created_at')
    search_fields = ('phone_number', 'user__username', 'current_step')
    list_filter = ('current_step',)

admin.site.register(WhatsAppSession, WhatsAppSessionAdmin)  

class InitiateSellOrdersAdmin(admin.ModelAdmin):
    list_display = ('trader', 'amount', 'ecocash_number', 'account_number', 'email')
    search_fields = ('trader__username', 'account_number', 'email')
    list_filter = ('amount',)

admin.site.register(InitiateSellOrders, InitiateSellOrdersAdmin)

class SwitchAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'is_active', 'off_message')
    search_fields = ('transaction_type',)
    list_filter = ('is_active',)
admin.site.register(Switch, SwitchAdmin)