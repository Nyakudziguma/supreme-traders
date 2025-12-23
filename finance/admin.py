# finance/admin.py
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import EcoCashTransaction, TransactionReceipt, TransactionCharge, BillingCycle

@admin.register(TransactionCharge)
class TransactionChargeAdmin(admin.ModelAdmin):
    list_display = ['range_display', 'charge_display', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active', 'is_percentage']
    readonly_fields = ['created_at', 'updated_at']
    
    def range_display(self, obj):
        if obj.is_percentage:
            return f"${obj.min_amount}+"
        else:
            return f"${obj.min_amount}-${obj.max_amount}"
    range_display.short_description = "Amount Range"
    
    def charge_display(self, obj):
        if obj.is_percentage:
            return f"{obj.percentage_rate}% + ${obj.additional_fee}"
        else:
            return f"${obj.fixed_charge}"
    charge_display.short_description = "Charge"
    
    def changelist_view(self, request, extra_context=None):
        # Check if charges are set up, if not, redirect to setup page
        if not TransactionCharge.objects.exists():
            self.message_user(request, "Please set up the transaction charges first.")
            return HttpResponseRedirect(reverse('admin:finance_transactioncharge_setup'))
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(EcoCashTransaction)
class EcoCashTransactionAdmin(admin.ModelAdmin):
    list_display = ['reference_number', 'user', 'transaction_type', 'amount', 'charge', 'currency', 'status', 'created_at']
    list_filter = ['status', 'transaction_type', 'currency', 'created_at']
    search_fields = ['reference_number', 'user__email', 'user__phone_number', 'ecocash_number', 'deriv_account_number']
    readonly_fields = ['reference_number', 'created_at', 'processed_at', 'charge']
    list_select_related = ['user']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('user', 'transaction_type', 'amount', 'currency', 'charge')
        }),
        ('Account Information', {
            'fields': ('deriv_account_number', 'ecocash_number', 'ecocash_name')
        }),
        ('Status & Tracking', {
            'fields': ('status', 'reference_number', 'ecocash_reference', 'deriv_transaction_id', 'ecocash_transaction_id', 'created_at', 'processed_at')
        }),
        ('Additional Information', {
            'fields': ('description', 'admin_notes')
        }),
    )

@admin.register(TransactionReceipt)
class TransactionReceiptAdmin(admin.ModelAdmin):
    list_display = ['transaction', 'receipt_number', 'uploaded_by', 'verified', 'uploaded_at']
    list_filter = ['verified', 'uploaded_at']
    search_fields = ['transaction__reference_number', 'receipt_number']
    readonly_fields = ['uploaded_at']


@admin.register(BillingCycle)
class BillingCycleAdmin(admin.ModelAdmin):
    list_display = (
        "client_name",
        "start_date",
        "end_date",
        "transactions_count",
        "amount_due",
        "paid",
    )
    list_filter = ("paid", "start_date", "end_date")
    search_fields = ("client_name",)
    actions = ["mark_as_paid"]

    def mark_as_paid(self, request, queryset):
        """Custom action to mark selected cycles as paid and start new ones."""
        for billing in queryset:
            if not billing.paid:
                billing.close_cycle()
        self.message_user(request, f"{queryset.count()} billing cycles marked as paid and new cycles started.")
    mark_as_paid.short_description = "Mark selected billing cycles as paid and start new cycles"
