from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomAuthenticationForm, ProfileUpdateForm, PasswordChangeForm
from django.contrib.auth import logout
import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
from django.urls import reverse

def signup(request):
    if request.user.is_authenticated:
        return redirect('admin_dashboard')
        
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully! Welcome to Henry Patson.')
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/signup.html', {'form': form})

def custom_login(request):
    if request.user.is_authenticated:
        return redirect('admin_dashboard')
        
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
                    
                    # Check if 2FA is enabled
                    if user.two_factor_enabled:
                        # Store user_id in session for 2FA verification
                        request.session['2fa_user_id'] = user.id
                        request.session['2fa_verified'] = False
                        
                        # Redirect to 2FA verification page
                        next_url = request.GET.get('next', 'admin_dashboard')
                        return redirect(f'{reverse("accounts:verify_2fa")}?next={next_url}')
                    else:
                        # Proceed to admin_dashboard directly
                        return redirect('admin_dashboard')
            else:
                messages.error(request, 'Invalid email/phone or password.')
        else:
            messages.error(request, 'Invalid email/phone or password.')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'accounts/login.html', {'form': form})


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

@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')

@login_required
def profile_view(request):
    """Profile settings page"""
    user = request.user
    
    # Generate 2FA QR code if not set up
    qr_code = None
    if not user.totp_secret:
        # Generate a new TOTP secret
        user.totp_secret = pyotp.random_base32()
        user.save(update_fields=['totp_secret'])
    
    # Create TOTP object
    totp = pyotp.TOTP(user.totp_secret)
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    # Create provisioning URI
    provisioning_uri = totp.provisioning_uri(
        name=user.email,
        issuer_name="Henry Patson Trading"
    )
    
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    
    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for embedding in HTML
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_code = base64.b64encode(buffer.getvalue()).decode()
    
    context = {
        'user': user,
        'qr_code': qr_code,
        'totp_secret': user.totp_secret,
    }
    
    return render(request, 'accounts/profile.html', context)

@login_required
def update_profile(request):
    """Update user profile information"""
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    
    return render(request, 'accounts/profile_update.html', {'form': form})

@login_required
def change_password(request):
    """Change user password"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})

@login_required
def toggle_2fa(request):
    """Enable/disable 2FA"""
    if request.method == 'POST':
        action = request.POST.get('action')
        code = request.POST.get('code')
        
        if action == 'enable':
            # Verify the code
            totp = pyotp.TOTP(request.user.totp_secret)
            if totp.verify(code):
                request.user.two_factor_enabled = True
                request.user.save()
                messages.success(request, 'Two-factor authentication enabled!')
            else:
                messages.error(request, 'Invalid verification code. Please try again.')
        
        elif action == 'disable':
            # Verify password first
            password = request.POST.get('password')
            if request.user.check_password(password):
                request.user.two_factor_enabled = False
                request.user.totp_secret = None
                request.user.save()
                messages.success(request, 'Two-factor authentication disabled!')
            else:
                messages.error(request, 'Incorrect password. Please try again.')
    
    return redirect('accounts:profile')

@login_required
def verify_2fa(request):
    """Verify 2FA code"""
    # Check if user has 2FA enabled and is not already verified
    if not request.user.two_factor_enabled:
        return redirect('admin_dashboard')
    
    if request.session.get('2fa_verified', False):
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        code = request.POST.get('code')
        
        # Verify the TOTP code
        totp = pyotp.TOTP(request.user.totp_secret)
        if totp.verify(code, valid_window=1):  # valid_window=1 allows for clock drift
            # Mark 2FA as verified in session
            request.session['2fa_verified'] = True
            messages.success(request, 'Two-factor authentication verified!')
            
            # Clear the stored user_id
            if '2fa_user_id' in request.session:
                del request.session['2fa_user_id']
            
            # Redirect to next page or admin_dashboard
            next_url = request.GET.get('next', 'admin_dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid verification code. Please try again.')
    
    return render(request, 'accounts/verify_2fa.html')