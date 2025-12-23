# whatsapp/forms.py
from django import forms
from .models import EcocashTransfers

class MoneyTransferForm(forms.ModelForm):
    class Meta:
        model = EcocashTransfers
        fields = ['transaction_type', 'ecocash_name', 'amount', 'ecocash_number']
        widgets = {
            'transaction_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-amber-500 focus:ring-2 focus:ring-amber-200 outline-none transition-all',
            }),
            'ecocash_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all',
                'placeholder': 'Recipient name (optional)',
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:ring-2 focus:ring-green-200 outline-none transition-all',
                'placeholder': 'Amount in USD',
                'min': '0.01',
                'step': '0.01',
            }),
            'ecocash_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:ring-2 focus:ring-green-200 outline-none transition-all',
                'placeholder': '077XXXXXXX',
            }),
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise forms.ValidationError('Amount must be greater than 0.')
        if amount and amount > 5000:
            raise forms.ValidationError('Maximum transfer amount is $5,000.')
        return amount
    
    # def clean_ecocash_number(self):
    #     number = self.cleaned_data.get('ecocash_number')
        # if number and not number.startswith('07'):
        #     raise forms.ValidationError('EcoCash number must start with 07.')
        # if number and len(number) != 10:
        #     raise forms.ValidationError('EcoCash number must be 10 digits.')
        # return number