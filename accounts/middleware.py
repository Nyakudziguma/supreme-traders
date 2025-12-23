from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class TwoFactorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.two_factor_enabled:
            # Skip 2FA check for certain paths
            exempt_paths = [
                reverse('accounts:logout'),
                reverse('accounts:profile'),
                reverse('accounts:toggle_2fa'),
                reverse('accounts:verify_2fa'),
                '/admin/',  # Admin paths if needed
            ]
            
            # Check if current path is exempt
            path_exempt = any(request.path.startswith(path) for path in exempt_paths)
            
            if not path_exempt and not request.session.get('2fa_verified', False):
                # Store the current path to redirect back after verification
                next_url = request.path
                if request.GET:
                    next_url += '?' + request.GET.urlencode()
                
                return redirect(f'{reverse("accounts:verify_2fa")}?next={next_url}')
        
        response = self.get_response(request)
        return response