from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomAuthenticationForm

def signup(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
        
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully! Welcome to Supreme AI.')
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/signup.html', {'form': form})

def custom_login(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
        
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            email_or_phone = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email_or_phone, password=password)
            if user is not None:
                if user.is_blocked:
                    messages.error(request, 'Your account has been suspended. Please contact support.')
                else:
                    login(request, user)
                    messages.success(request, f'Welcome back, {user.email}!')
                    return redirect('accounts:dashboard')
            else:
                messages.error(request, 'Invalid email/phone or password.')
        else:
            messages.error(request, 'Invalid email/phone or password.')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def dashboard(request):
    if request.user.user_type == 'admin':
        return render(request, 'dashboard/admin_dashboard.html')
    else:
        return render(request, 'dashboard/user_dashboard.html')

@login_required
def profile(request):
    return render(request, 'accounts/profile.html')

@login_required
def profile_update(request):
    if request.method == 'POST':
        # Handle profile update logic here
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')
    return render(request, 'accounts/profile_update.html')