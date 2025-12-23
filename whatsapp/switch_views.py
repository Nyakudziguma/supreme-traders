# switches/views.py
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.http import JsonResponse
from .models import Switch

def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

@login_required
@user_passes_test(is_admin)
def switch_list(request):
    """List all switches"""
    switches = Switch.objects.all().order_by('transaction_type')
    
    # Get counts
    active_count = switches.filter(is_active=True).count()
    inactive_count = switches.filter(is_active=False).count()
    
    context = {
        'switches': switches,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'total_count': switches.count(),
    }
    return render(request, 'switches/list.html', context)

@login_required
@user_passes_test(is_admin)
def switch_toggle(request, pk):
    """Toggle switch on/off"""
    switch = get_object_or_404(Switch, pk=pk)
    
    if request.method == 'POST':
        try:
            # Toggle the switch
            switch.is_active = not switch.is_active
            switch.save()
            
            status = 'activated' if switch.is_active else 'deactivated'
            messages.success(request, f'{switch.get_transaction_type_display()} switch has been {status}')
            
            return redirect('switches:switch_list')
            
        except Exception as e:
            messages.error(request, f'Error toggling switch: {str(e)}')
    
    return redirect('switches:switch_list')

@login_required
@user_passes_test(is_admin)
def switch_edit(request, pk=None):
    """Create or edit a switch"""
    if pk:
        switch = get_object_or_404(Switch, pk=pk)
        is_edit = True
    else:
        switch = None
        is_edit = False
    
    if request.method == 'POST':
        try:
            transaction_type = request.POST.get('transaction_type')
            off_message = request.POST.get('off_message', '').strip()
            on_message = request.POST.get('on_message', '').strip()
            
            if is_edit:
                # Update existing switch
                switch.transaction_type = transaction_type
                switch.off_message = off_message
                switch.on_message = on_message
                switch.save()
                
                messages.success(request, f'{switch.get_transaction_type_display()} switch updated successfully')
            else:
                # Create new switch
                switch = Switch.objects.create(
                    transaction_type=transaction_type,
                    off_message=off_message,
                    on_message=on_message,
                    is_active=True
                )
                
                messages.success(request, f'{switch.get_transaction_type_display()} switch created successfully')
            
            return redirect('switches:switch_list')
            
        except Exception as e:
            messages.error(request, f'Error saving switch: {str(e)}')
    
    context = {
        'switch': switch,
        'is_edit': is_edit,
        'transaction_types': Switch.Transaction_Types,
    }
    return render(request, 'switches/edit.html', context)

@login_required
@user_passes_test(is_admin)
def switch_delete(request, pk):
    """Delete a switch"""
    switch = get_object_or_404(Switch, pk=pk)
    
    if request.method == 'POST':
        try:
            switch_name = switch.get_transaction_type_display()
            switch.delete()
            messages.success(request, f'{switch_name} switch deleted successfully')
            return redirect('switches:switch_list')
        except Exception as e:
            messages.error(request, f'Error deleting switch: {str(e)}')
    
    return redirect('switches:switch_list')

@login_required
@user_passes_test(is_admin)
def switch_bulk_toggle(request):
    """Bulk toggle switches"""
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            switch_ids = request.POST.getlist('switch_ids')
            
            if not switch_ids:
                messages.warning(request, 'Please select at least one switch')
                return redirect('switches:switch_list')
            
            switches = Switch.objects.filter(id__in=switch_ids)
            
            if action == 'activate':
                updated_count = switches.filter(is_active=False).update(is_active=True)
                messages.success(request, f'{updated_count} switch(es) activated')
            elif action == 'deactivate':
                updated_count = switches.filter(is_active=True).update(is_active=False)
                messages.success(request, f'{updated_count} switch(es) deactivated')
            elif action == 'delete':
                deleted_count, _ = switches.delete()
                messages.success(request, f'{deleted_count} switch(es) deleted')
            
            return redirect('switches:switch_list')
            
        except Exception as e:
            messages.error(request, f'Error performing bulk action: {str(e)}')
    
    return redirect('switches:switch_list')

@login_required
@user_passes_test(is_admin)
def switch_check_status(request, switch_type):
    """Check if a switch is active (API endpoint)"""
    try:
        switch = Switch.objects.filter(transaction_type=switch_type).first()
        
        if switch:
            return JsonResponse({
                'exists': True,
                'is_active': switch.is_active,
                'off_message': switch.off_message,
                'on_message': switch.on_message,
                'type': switch.get_transaction_type_display(),
            })
        else:
            return JsonResponse({
                'exists': False,
                'is_active': False,
                'message': f'No switch found for {switch_type}'
            })
            
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=400)