# finance/forms.py
from django import forms
from .models import EcoCashTransaction, TransactionCharge

class AdminTransactionForm(forms.ModelForm):
    class Meta:
        model = EcoCashTransaction
        fields = [
            'user', 'transaction_type', 'amount', 'currency',
            'deriv_account_number', 'ecocash_number', 'ecocash_name',
            'charge', 'status', 'description'
        ]
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'deriv_account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'ecocash_number': forms.TextInput(attrs={'class': 'form-control'}),
            'ecocash_name': forms.TextInput(attrs={'class': 'form-control'}),
            'charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class TransactionChargeForm(forms.ModelForm):
    class Meta:
        model = TransactionCharge
        fields = [
            'min_amount', 'max_amount', 'fixed_charge', 
            'is_percentage', 'percentage_rate', 'additional_fee', 'is_active'
        ]
        widgets = {
            'min_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fixed_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'percentage_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'additional_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_percentage': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }