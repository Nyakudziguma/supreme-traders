from django.contrib import admin

from django.contrib import admin
from .models import IncomingMessage, IncomingCall, OutgoingMessage, EcocashTransfers

@admin.register(IncomingMessage)
class IncomingMessageAdmin(admin.ModelAdmin):
    list_display = ('sender_id', 'message_body', 'received_at')
    search_fields = ('sender_id', 'message_body')
    list_filter = ('received_at', 'sender_id',)

@admin.register(IncomingCall)
class IncomingCallAdmin(admin.ModelAdmin):
    list_display = ('caller_id', 'call_time', 'duration_seconds')


@admin.register(OutgoingMessage)
class OutgoingMessageAdmin(admin.ModelAdmin):
    list_display = ('recipient_id', 'message_body', 'sent_at')

@admin.register(EcocashTransfers)
class EcocashTransfersAdmin(admin.ModelAdmin):
    list_display = ('user', 'transaction_type', 'amount', 'ecocash_number', 'status', 'reference_number', 'created_at')
    search_fields = ('user__email', 'ecocash_number', 'reference_number')
    list_filter = ('status', 'transaction_type', 'created_at')