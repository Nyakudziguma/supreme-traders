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
            'user': forms.Select(attrs={
                'class': 'form-select'
            }),
            'transaction_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'currency': forms.Select(attrs={
                'class': 'form-select'
            }),
            'deriv_account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'CR0000000'
            }),
            'ecocash_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '077XXXXXXX'
            }),
            'ecocash_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full name as registered on EcoCash'
            }),
            'charge': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'readonly': True
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Add any additional notes or description...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add help text and labels
        self.fields['deriv_account_number'].help_text = "Must start with 'CR' followed by numbers"
        self.fields['ecocash_number'].help_text = "EcoCash number in Zimbabwean format"
        self.fields['amount'].label = "Total Amount (USD)"
        self.fields['charge'].label = "Transaction Charge"
        
        # Style each field
        for field_name, field in self.fields.items():
            if field.widget.__class__.__name__ in ['Select', 'NumberInput', 'TextInput', 'Textarea']:
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-3 border-2 border-amber-300 rounded-xl focus:border-amber-500 focus:ring-2 focus:ring-amber-200 outline-none transition-all duration-200 bg-white shadow-sm'
                })

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