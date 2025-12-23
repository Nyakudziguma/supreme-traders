# signals/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
import json

from .models import Signal, SignalRecipient, WhatsAppTemplate, BulkSignalJob, Subscribers, SubscriptionPlans
from whatsapp.services import WhatsAppService

@login_required
def signal_dashboard(request):
    """Signal management dashboard"""
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('accounts:dashboard')
    
    # Statistics
    total_signals = Signal.objects.count()
    pending_signals = Signal.objects.filter(status='draft').count()
    sent_today = Signal.objects.filter(
        status='sent', 
        sent_at__date=timezone.now().date()
    ).count()
    
    # Recent signals
    recent_signals = Signal.objects.all().order_by('-created_at')[:5]
    
    # Active subscribers
    active_subscribers = Subscribers.objects.filter(active=True).count()
    
    # Bulk job stats
    recent_jobs = BulkSignalJob.objects.all().order_by('-created_at')[:5]
    
    context = {
        'total_signals': total_signals,
        'pending_signals': pending_signals,
        'sent_today': sent_today,
        'active_subscribers': active_subscribers,
        'recent_signals': recent_signals,
        'recent_jobs': recent_jobs,
    }
    
    return render(request, 'signals/dashboard.html', context)

@login_required
def signal_list(request):
    """List all trading signals"""
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('accounts:dashboard')
    
    # Filters
    signal_type = request.GET.get('type')
    status = request.GET.get('status')
    asset_type = request.GET.get('asset_type')
    search = request.GET.get('search')
    
    signals = Signal.objects.all()
    
    if signal_type:
        signals = signals.filter(signal_type=signal_type)
    
    if status:
        signals = signals.filter(status=status)
    
    if asset_type:
        signals = signals.filter(asset_type=asset_type)
    
    if search:
        signals = signals.filter(
            Q(asset_pair__icontains=search) |
            Q(title__icontains=search) |
            Q(signal_id__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(signals, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'filter_type': signal_type,
        'filter_status': status,
        'filter_asset': asset_type,
        'search_query': search,
    }
    
    return render(request, 'signals/signal_list.html', context)

@login_required
def create_signal(request):
    """Create new trading signal"""
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        # Extract form data
        title = request.POST.get('title')
        signal_type = request.POST.get('signal_type')
        asset_type = request.POST.get('asset_type')
        asset_pair = request.POST.get('asset_pair')
        
        # Create signal
        signal = Signal.objects.create(
            title=title,
            signal_type=signal_type,
            asset_type=asset_type,
            asset_pair=asset_pair,
            entry_price=request.POST.get('entry_price') or None,
            stop_loss=request.POST.get('stop_loss') or None,
            take_profit_1=request.POST.get('take_profit_1') or None,
            take_profit_2=request.POST.get('take_profit_2') or None,
            take_profit_3=request.POST.get('take_profit_3') or None,
            analysis=request.POST.get('analysis', ''),
            confidence_level=request.POST.get('confidence_level', 50),
            risk_level=request.POST.get('risk_level', 'medium'),
            valid_until=request.POST.get('valid_until') or None,
            whatsapp_template=request.POST.get('whatsapp_template', ''),
            created_by=request.user,
            status='draft'
        )
        
        messages.success(request, f"Signal {signal.signal_id} created successfully!")
        return redirect('signals:signal_detail', pk=signal.pk)
    
    # Get WhatsApp templates
    templates = WhatsAppTemplate.objects.filter(is_active=True)
    
    context = {
        'templates': templates,
    }
    
    return render(request, 'signals/create_signal.html', context)

@login_required
def signal_detail(request, pk):
    """View and manage individual signal"""
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('accounts:dashboard')
    
    signal = get_object_or_404(Signal, pk=pk)
    
    # Get recipients
    recipients = SignalRecipient.objects.filter(signal=signal)
    
    # Get bulk jobs for this signal
    bulk_jobs = BulkSignalJob.objects.filter(signal=signal)
    
    context = {
        'signal': signal,
        'recipients': recipients,
        'bulk_jobs': bulk_jobs,
    }
    
    return render(request, 'signals/signal_detail.html', context)

@login_required
def edit_signal(request, pk):
    """Edit existing signal"""
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('accounts:dashboard')
    
    signal = get_object_or_404(Signal, pk=pk)
    
    if request.method == 'POST':
        # Update signal
        signal.title = request.POST.get('title')
        signal.signal_type = request.POST.get('signal_type')
        signal.asset_type = request.POST.get('asset_type')
        signal.asset_pair = request.POST.get('asset_pair')
        signal.entry_price = request.POST.get('entry_price') or None
        signal.stop_loss = request.POST.get('stop_loss') or None
        signal.take_profit_1 = request.POST.get('take_profit_1') or None
        signal.take_profit_2 = request.POST.get('take_profit_2') or None
        signal.take_profit_3 = request.POST.get('take_profit_3') or None
        signal.analysis = request.POST.get('analysis', '')
        signal.confidence_level = request.POST.get('confidence_level', 50)
        signal.risk_level = request.POST.get('risk_level', 'medium')
        signal.valid_until = request.POST.get('valid_until') or None
        signal.whatsapp_template = request.POST.get('whatsapp_template', '')
        signal.status = request.POST.get('status', 'draft')
        signal.save()
        
        messages.success(request, f"Signal {signal.signal_id} updated successfully!")
        return redirect('signals:signal_detail', pk=signal.pk)
    
    # Get WhatsApp templates
    templates = WhatsAppTemplate.objects.filter(is_active=True)
    
    context = {
        'signal': signal,
        'templates': templates,
    }
    
    return render(request, 'signals/edit_signal.html', context)

@login_required
def send_bulk_signal(request, pk):
    """Send signal to multiple subscribers"""
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('accounts:dashboard')
    
    signal = get_object_or_404(Signal, pk=pk)
    
    if request.method == 'POST':
        # Get recipients filter
        plan_id = request.POST.get('plan_filter')
        send_to_all = request.POST.get('send_to_all') == 'on'
        
        # Get active subscribers
        subscribers = Subscribers.objects.filter(active=True)
        
        if plan_id:
            subscribers = subscribers.filter(plan_id=plan_id)
        
        if not send_to_all and not plan_id:
            messages.error(request, "Please select either a plan or 'Send to all active'")
            return redirect('signals:send_bulk_signal', pk=pk)
        
        # Create bulk job
        bulk_job = BulkSignalJob.objects.create(
            signal=signal,
            initiated_by=request.user,
            plan_filter_id=plan_id,
            send_to_all_active=send_to_all,
            total_recipients=subscribers.count(),
            status='pending'
        )
        
        # Start sending in background (you can use Celery for this)
        # For now, we'll simulate
        messages.success(request, f"Bulk job created. {subscribers.count()} recipients will receive the signal.")
        return redirect('signals:bulk_job_detail', pk=bulk_job.pk)
    
    # Get available plans
    plans = SubscriptionPlans.objects.all()
    
    # Get subscriber counts
    total_active = Subscribers.objects.filter(active=True).count()
    plan_counts = {}
    for plan in plans:
        count = Subscribers.objects.filter(plan=plan, active=True).count()
        if count > 0:
            plan_counts[plan.id] = count
    
    context = {
        'signal': signal,
        'plans': plans,
        'total_active': total_active,
        'plan_counts': plan_counts,
    }
    
    return render(request, 'signals/send_bulk.html', context)

@login_required
def bulk_jobs_list(request):
    """List all bulk signal jobs"""
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('accounts:dashboard')
    
    jobs = BulkSignalJob.objects.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(jobs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'signals/bulk_jobs_list.html', context)

@login_required
def bulk_job_detail(request, pk):
    """View bulk job details"""
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('accounts:dashboard')
    
    job = get_object_or_404(BulkSignalJob, pk=pk)
    
    # Get recipients
    recipients = SignalRecipient.objects.filter(
        signal=job.signal,
        subscriber__in=Subscribers.objects.filter(active=True)
    )
    
    context = {
        'job': job,
        'recipients': recipients,
    }
    
    return render(request, 'signals/bulk_job_detail.html', context)

@login_required
def whatsapp_templates(request):
    """Manage WhatsApp templates"""
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('accounts:dashboard')
    
    templates = WhatsAppTemplate.objects.all()
    
    context = {
        'templates': templates,
    }
    
    return render(request, 'signals/whatsapp_templates.html', context)

@login_required
@require_POST
def send_test_signal(request, pk):
    """Send test signal to admin's WhatsApp"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    signal = get_object_or_404(Signal, pk=pk)
    
    try:
        # Get formatted message
        message = signal.get_formatted_message()
        
        # Initialize WhatsApp manager
        whatsapp_manager = WhatsAppService()
        
        # Send to admin's phone (you need to store admin's WhatsApp number)
        admin_phone = request.user.phone_number  # Adjust based on your user model
        
        if admin_phone:
            result = whatsapp_manager.send_message(
                phone_number=admin_phone,
                message=message
            )
            
            if result.get('success'):
                return JsonResponse({'success': True, 'message': 'Test signal sent successfully!'})
            else:
                return JsonResponse({'success': False, 'error': result.get('error', 'Failed to send')})
        else:
            return JsonResponse({'success': False, 'error': 'Admin phone number not found'})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def subscriber_management(request):
    """Manage subscribers"""
    if not request.user.is_staff:
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('accounts:dashboard')
    
    # Filters
    plan_id = request.GET.get('plan')
    status = request.GET.get('status')
    search = request.GET.get('search')
    
    subscribers = Subscribers.objects.select_related('trader', 'plan')
    
    if plan_id:
        subscribers = subscribers.filter(plan_id=plan_id)
    
    if status == 'active':
        subscribers = subscribers.filter(active=True)
    elif status == 'expired':
        subscribers = subscribers.filter(active=False)
    
    if search:
        subscribers = subscribers.filter(
            Q(trader__email__icontains=search) |
            Q(trader__phone_number__icontains=search) |
            Q(ecocash_number__icontains=search)
        )
    
    # Statistics
    total_subscribers = subscribers.count()
    active_subscribers = subscribers.filter(active=True).count()
    
    # Get plans for filter
    plans = SubscriptionPlans.objects.all()
    
    # Pagination
    paginator = Paginator(subscribers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_subscribers': total_subscribers,
        'active_subscribers': active_subscribers,
        'plans': plans,
        'filter_plan': plan_id,
        'filter_status': status,
        'search_query': search,
    }
    
    return render(request, 'signals/subscriber_management.html', context)

@login_required
@require_POST
def toggle_subscriber_status(request, pk):
    """Activate/deactivate subscriber"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    subscriber = get_object_or_404(Subscribers, pk=pk)
    
    try:
        subscriber.active = not subscriber.active
        subscriber.save()
        
        status = "activated" if subscriber.active else "deactivated"
        return JsonResponse({
            'success': True, 
            'message': f'Subscriber {status} successfully!',
            'is_active': subscriber.active
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})