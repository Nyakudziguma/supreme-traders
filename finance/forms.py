# finance/forms.py
from django import forms
from .models import EcoCashTransaction, TransactionCharge
from ecocash.models import CashOutTransaction
from accounts.models import User
import re

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

class CashOutTransactionForm(forms.ModelForm):
    class Meta:
        model = CashOutTransaction
        fields = [
            'amount', 'name', 'phone', 'txn_id', 'body', 
            'completed', 'trader', 'verification_code',
            'prev_bal', 'new_bal', 'flagged', 'fradulent',
            'low_limit', 'flag_reason', 'flagged_by'
        ]
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Customer Name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 0712345678, 0771234567, or +263712345678'
            }),
            'txn_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'eg CO260124.1851.T00000'
            }),
            'body': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Transaction message/details'
            }),
            'verification_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leave empty to auto-generate'
            }),
            'prev_bal': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'new_bal': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'flag_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Reason for flagging'
            }),
            'flagged_by': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Admin name who flagged'
            }),
        }
    
    trader = forms.ModelChoiceField(
        queryset=User.objects.filter(is_staff=False).order_by('email'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial values
        if not self.instance.pk:
            self.fields['prev_bal'].initial = 0
            self.fields['new_bal'].initial = 0
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        
        if not phone:
            raise forms.ValidationError('Phone number is required')
        
        # Clean the phone number to get only local mobile number
        cleaned_phone = self.normalize_phone_number(phone)
        
        # Validate the cleaned phone number
        if not self.validate_phone_number(cleaned_phone):
            raise forms.ValidationError(
                'Please enter a valid Zimbabwean mobile number (starting with 71, 73, 77, 78, 79)'
            )
        
        return cleaned_phone
    
    def normalize_phone_number(self, phone):
        """Extract only the local mobile number without zero or country code"""
        # Remove all non-digit characters
        phone = re.sub(r'[^\d]', '', phone)
        
        # Remove leading zeros
        phone = phone.lstrip('0')
        
        # Remove country code if present
        if phone.startswith('263'):
            phone = phone[3:]
        
        # Ensure it's exactly 9 digits
        if len(phone) != 9:
            # If shorter than 9, pad with zeros at the end (unlikely but just in case)
            # If longer than 9, truncate (also unlikely)
            phone = phone[:9].ljust(9, '0')
        
        return phone
    
    def validate_phone_number(self, phone):
        """Validate local mobile number format (9 digits starting with valid prefix)"""
        # Should be exactly 9 digits
        if not re.match(r'^\d{9}$', phone):
            return False
        
        # Check if the mobile prefix is valid for Zimbabwe
        # Valid prefixes: 71, 73, 77, 78, 79
        mobile_prefix = phone[:2]
        valid_prefixes = ['71', '73', '77', '78', '79']
        
        return mobile_prefix in valid_prefixes
    
    def clean_txn_id(self):
        txn_id = self.cleaned_data.get('txn_id', '').strip()
        
        if not txn_id:
            raise forms.ValidationError('Transaction ID is required')
        
      
        # Ensure there are numbers after SPFX
        numbers_part = txn_id[4:]

      
        return txn_id.upper()  # Convert to uppercase for consistency
