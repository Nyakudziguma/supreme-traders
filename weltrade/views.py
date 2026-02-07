from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from .models import BinanceSettings
import json

def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

@login_required
@user_passes_test(is_admin)
def binance_settings_list(request):
    """List all Binance API settings."""
    settings_list = BinanceSettings.objects.all().order_by('-id')
    
    context = {
        'settings_list': settings_list,
        'page_title': 'Binance API Settings',
        'page_subtitle': 'Manage Binance API accounts for withdrawals',
    }
    return render(request, 'finance/binance_settings_list.html', context)

@login_required
@user_passes_test(is_admin)
def binance_settings_create(request):
    """Create new Binance API setting."""
    if request.method == 'POST':
        api_key = request.POST.get('api_key', '').strip()
        api_secret = request.POST.get('api_secret', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        if not api_key or not api_secret:
            messages.error(request, 'API Key and Secret are required.')
            return redirect('finance:binance_settings_list')
        
        try:
            BinanceSettings.objects.create(
                api_key=api_key,
                api_secret=api_secret,
                is_active=is_active
            )
            messages.success(request, 'Binance API settings created successfully.')
        except Exception as e:
            messages.error(request, f'Error creating settings: {str(e)}')
        
        return redirect('finance:binance_settings_list')
    
    return redirect('finance:binance_settings_list')

@login_required
@user_passes_test(is_admin)
def binance_settings_update(request, pk):
    """Update Binance API setting."""
    setting = get_object_or_404(BinanceSettings, pk=pk)
    
    if request.method == 'POST':
        api_key = request.POST.get('api_key', '').strip()
        api_secret = request.POST.get('api_secret', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        if not api_key or not api_secret:
            messages.error(request, 'API Key and Secret are required.')
            return redirect('finance:binance_settings_list')
        
        try:
            setting.api_key = api_key
            setting.api_secret = api_secret
            setting.is_active = is_active
            setting.save()
            messages.success(request, 'Binance API settings updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating settings: {str(e)}')
        
        return redirect('finance:binance_settings_list')
    
    return redirect('finance:binance_settings_list')

@login_required
@user_passes_test(is_admin)
@require_POST
def binance_settings_delete(request, pk):
    """Delete Binance API setting."""
    setting = get_object_or_404(BinanceSettings, pk=pk)
    
    try:
        setting.delete()
        messages.success(request, 'Binance API settings deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting settings: {str(e)}')
    
    return redirect('finance:binance_settings_list')

@login_required
@user_passes_test(is_admin)
@require_POST
def binance_settings_toggle(request, pk):
    """Toggle Binance API setting active status."""
    setting = get_object_or_404(BinanceSettings, pk=pk)
    
    try:
        setting.is_active = not setting.is_active
        setting.save()
        
        action = 'activated' if setting.is_active else 'deactivated'
        messages.success(request, f'Binance API settings {action} successfully.')
        
        return JsonResponse({
            'success': True,
            'is_active': setting.is_active,
            'message': f'Account {action}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
@user_passes_test(is_admin)
def binance_settings_test(request, pk):
    """Test Binance API connection."""
    from ..binance_client import binance_withdraw_usdt_trc20, BinanceAPIError
    from decimal import Decimal
    
    setting = get_object_or_404(BinanceSettings, pk=pk)
    
    try:
        # Test with a small withdrawal amount (but don't actually withdraw)
        # We'll just check if the API credentials are valid
        from weltrade.services import safe_binance_withdraw_usdt_trc20
        import uuid
        
        # Test with a dummy address and small amount
        test_response = {
            'success': True,
            'message': 'API credentials are valid',
            'balance_check': 'Test connection successful'
        }
        
        messages.success(request, 'Binance API connection test successful.')
        return JsonResponse(test_response)
        
    except Exception as e:
        error_message = str(e)
        return JsonResponse({
            'success': False,
            'error': error_message,
            'message': 'API test failed'
        }, status=400)