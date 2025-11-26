# accounts/.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import User
from django.contrib.auth.forms import AuthenticationForm

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='Email or Phone Number',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 appearance-none relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-lg focus:outline-none focus:ring-amber focus:border-amber focus:z-10',
            'placeholder': 'Enter your email or phone number'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 appearance-none relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-lg focus:outline-none focus:ring-amber focus:border-amber focus:z-10',
            'placeholder': 'Enter your password'
        })
    )
    

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'mt-1 appearance-none relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-lg focus:outline-none focus:ring-amber focus:border-amber focus:z-10',
            'placeholder': 'Enter your email address'
        })
    )
    
    phone_number = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'mt-1 appearance-none relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-lg focus:outline-none focus:ring-amber focus:border-amber focus:z-10',
            'placeholder': 'Enter your WhatsApp number'
        })
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 appearance-none relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-lg focus:outline-none focus:ring-amber focus:border-amber focus:z-10',
            'placeholder': 'Create a password'
        })
    )
    
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 appearance-none relative block w-full px-3 py-3 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-lg focus:outline-none focus:ring-amber focus:border-amber focus:z-10',
            'placeholder': 'Confirm your password'
        })
    )

    class Meta:
        model = User
        fields = ('email', 'phone_number', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number']
        if User.objects.filter(phone_number=phone_number).exists():
            raise ValidationError("A user with this phone number already exists.")
        return phone_number
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.phone_number = self.cleaned_data['phone_number']
        # Auto-generate username from email
        user.username = self.cleaned_data['email'].split('@')[0]
        if commit:
            user.save()
        return user