# marketing/views.py
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import json
from .models import Marketing
from accounts.models import User
from finance.models import EcoCashTransaction

def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

@login_required
@user_passes_test(is_admin)
def marketing_dashboard(request):
    """Marketing dashboard with stats and campaigns"""
    # Calculate stats
    total_campaigns = Marketing.objects.count()
    active_campaigns = Marketing.objects.filter(is_active=True).count()
    sent_campaigns = Marketing.objects.filter(is_sent=True).count()
    scheduled_campaigns = Marketing.objects.filter(
        scheduled_for__gt=timezone.now(),
        is_sent=False
    ).count()
    
    # Recent campaigns
    recent_campaigns = Marketing.objects.all().order_by('-created_at')[:5]
    
    # Campaigns by type
    campaigns_by_type = Marketing.objects.values('message_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Performance metrics
    top_performing = Marketing.objects.filter(
        total_sent__gt=0
    ).order_by('-open_rate')[:5]
    
    context = {
        'total_campaigns': total_campaigns,
        'active_campaigns': active_campaigns,
        'sent_campaigns': sent_campaigns,
        'scheduled_campaigns': scheduled_campaigns,
        'recent_campaigns': recent_campaigns,
        'campaigns_by_type': campaigns_by_type,
        'top_performing': top_performing,
    }
    return render(request, 'marketing/dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def marketing_campaign_list(request):
    """List all marketing campaigns"""
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    type_filter = request.GET.get('type', 'all')
    
    campaigns = Marketing.objects.all().order_by('-created_at')
    
    # Apply filters
    if search_query:
        campaigns = campaigns.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query)
        )
    
    if status_filter != 'all':
        if status_filter == 'draft':
            campaigns = campaigns.filter(is_sent=False, scheduled_for__isnull=True)
        elif status_filter == 'scheduled':
            campaigns = campaigns.filter(
                scheduled_for__gt=timezone.now(),
                is_sent=False
            )
        elif status_filter == 'sent':
            campaigns = campaigns.filter(is_sent=True)
        elif status_filter == 'active':
            campaigns = campaigns.filter(is_active=True)
    
    if type_filter != 'all':
        campaigns = campaigns.filter(message_type=type_filter)
    
    # Pagination
    paginator = Paginator(campaigns, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'campaigns': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'type_filter': type_filter,
    }
    return render(request, 'marketing/campaign_list.html', context)

@login_required
@user_passes_test(is_admin)
def marketing_campaign_create(request):
    """Create a new marketing campaign"""
    if request.method == 'POST':
        try:
            # Create campaign
            campaign = Marketing.objects.create(
                title=request.POST.get('title'),
                content=request.POST.get('content'),
                message_type=request.POST.get('message_type', 'marketing'),
                audience_type=request.POST.get('audience_type', 'all_users'),
                send_immediately=request.POST.get('send_immediately') == 'true',
                created_by=request.user
            )
            
            # Handle scheduled send
            scheduled_date = request.POST.get('scheduled_date')
            scheduled_time = request.POST.get('scheduled_time')
            
            if scheduled_date and scheduled_time and not campaign.send_immediately:
                from datetime import datetime
                scheduled_datetime = datetime.strptime(
                    f"{scheduled_date} {scheduled_time}",
                    "%Y-%m-%d %H:%M"
                )
                campaign.scheduled_for = scheduled_datetime
                campaign.save()
            
            # Handle image upload
            if 'image' in request.FILES:
                campaign.image = request.FILES['image']
            
            # Handle attachment
            if 'attachment' in request.FILES:
                campaign.attachment = request.FILES['attachment']
            
            campaign.save()
            
            messages.success(request, f'Campaign "{campaign.title}" created successfully')
            
            # Send immediately if requested
            if campaign.send_immediately and not campaign.scheduled_for:
                # Here you would integrate with your messaging system
                # For now, we'll just mark as sent
                campaign.is_sent = True
                campaign.sent_at = timezone.now()
                campaign.save()
                messages.success(request, f'Campaign sent to {campaign.get_audience_count()} users')
            
            return redirect('marketing:campaign_detail', pk=campaign.pk)
            
        except Exception as e:
            messages.error(request, f'Error creating campaign: {str(e)}')
    
    return render(request, 'marketing/campaign_create.html')

@login_required
@user_passes_test(is_admin)
def marketing_campaign_detail(request, pk):
    """View campaign details"""
    campaign = get_object_or_404(Marketing, pk=pk)
    
    # Get campaign metrics
    metrics = {
        'delivery_rate': (campaign.total_delivered / campaign.total_sent * 100) if campaign.total_sent > 0 else 0,
        'open_rate': campaign.open_rate,
        'click_rate': campaign.click_rate,
        'audience_count': campaign.get_audience_count(),
    }
    
    context = {
        'campaign': campaign,
        'metrics': metrics,
    }
    return render(request, 'marketing/campaign_detail.html', context)

@login_required
@user_passes_test(is_admin)
def marketing_campaign_edit(request, pk):
    """Edit a marketing campaign"""
    campaign = get_object_or_404(Marketing, pk=pk)
    
    if request.method == 'POST':
        try:
            # Update campaign
            campaign.title = request.POST.get('title')
            campaign.content = request.POST.get('content')
            campaign.message_type = request.POST.get('message_type', 'marketing')
            campaign.audience_type = request.POST.get('audience_type', 'all_users')
            campaign.send_immediately = request.POST.get('send_immediately') == 'true'
            
            # Handle scheduled send
            scheduled_date = request.POST.get('scheduled_date')
            scheduled_time = request.POST.get('scheduled_time')
            
            if scheduled_date and scheduled_time and not campaign.send_immediately:
                from datetime import datetime
                scheduled_datetime = datetime.strptime(
                    f"{scheduled_date} {scheduled_time}",
                    "%Y-%m-%d %H:%M"
                )
                campaign.scheduled_for = scheduled_datetime
            else:
                campaign.scheduled_for = None
            
            # Handle image upload
            if 'image' in request.FILES:
                campaign.image = request.FILES['image']
            
            # Handle attachment
            if 'attachment' in request.FILES:
                campaign.attachment = request.FILES['attachment']
            
            campaign.save()
            
            messages.success(request, f'Campaign "{campaign.title}" updated successfully')
            return redirect('marketing:campaign_detail', pk=campaign.pk)
            
        except Exception as e:
            messages.error(request, f'Error updating campaign: {str(e)}')
    
    context = {
        'campaign': campaign,
    }
    return render(request, 'marketing/campaign_edit.html', context)

@login_required
@user_passes_test(is_admin)
def marketing_campaign_send(request, pk):
    """Send a marketing campaign"""
    campaign = get_object_or_404(Marketing, pk=pk)
    
    if request.method == 'POST':
        try:
            if campaign.is_sent:
                messages.warning(request, f'Campaign "{campaign.title}" has already been sent')
            else:
                # Here you would integrate with your actual messaging system
                # For WhatsApp, SMS, Email, etc.
                
                # Get audience
                audience_count = campaign.get_audience_count()
                
                # Simulate sending
                campaign.is_sent = True
                campaign.sent_at = timezone.now()
                campaign.total_sent = audience_count
                campaign.total_delivered = audience_count  # Simulate 100% delivery
                campaign.save()
                
                messages.success(request, f'Campaign sent to {audience_count} users successfully')
            
            return redirect('marketing:campaign_detail', pk=campaign.pk)
            
        except Exception as e:
            messages.error(request, f'Error sending campaign: {str(e)}')
    
    return redirect('marketing:campaign_detail', pk=campaign.pk)

@login_required
@user_passes_test(is_admin)
def marketing_campaign_delete(request, pk):
    """Delete a marketing campaign"""
    campaign = get_object_or_404(Marketing, pk=pk)
    
    if request.method == 'POST':
        try:
            campaign_title = campaign.title
            campaign.delete()
            messages.success(request, f'Campaign "{campaign_title}" deleted successfully')
            return redirect('marketing:campaign_list')
        except Exception as e:
            messages.error(request, f'Error deleting campaign: {str(e)}')
    
    return redirect('marketing:campaign_detail', pk=campaign.pk)

@login_required
@user_passes_test(is_admin)
def marketing_template_list(request):
    """List of marketing templates"""
    templates = [
        {
            'id': 1,
            'name': 'Transaction Success',
            'type': 'transaction_success',
            'content': '🎉 Transaction Successful!\n\nYour deposit of ${amount} has been processed successfully!\n\nTransaction ID: {transaction_id}\nAccount: {account_number}\n\nThank you for using Henry Patson!',
            'variables': ['amount', 'transaction_id', 'account_number']
        },
        {
            'id': 2,
            'name': 'Welcome Message',
            'type': 'welcome',
            'content': '👋 Welcome to Henry Patson!\n\nWe\'re excited to have you on board!\n\nStart your trading journey with us and experience intelligent trading signals.\n\nNeed help? Contact our support team.',
            'variables': []
        },
        {
            'id': 3,
            'name': 'Promotional Offer',
            'type': 'promotional',
            'content': '🔥 Special Offer!\n\nGet 20% bonus on your next deposit!\n\nUse code: SUPREME20\n\nValid until {expiry_date}\n\nLimited time offer!',
            'variables': ['expiry_date']
        },
        {
            'id': 4,
            'name': 'Educational Content',
            'type': 'educational',
            'content': '📚 Trading Tip of the Day!\n\n{tip_content}\n\nStay informed and trade smarter with Henry Patson!\n\nHappy trading!',
            'variables': ['tip_content']
        },
        {
            'id': 5,
            'name': 'System Maintenance',
            'type': 'system',
            'content': '⚠️ System Maintenance Notice\n\nWe\'ll be performing system maintenance on {date} from {start_time} to {end_time}.\n\nServices may be temporarily unavailable.\n\nThank you for your patience!',
            'variables': ['date', 'start_time', 'end_time']
        },
    ]
    
    context = {
        'templates': templates,
    }
    return render(request, 'marketing/template_list.html', context)

@login_required
@user_passes_test(is_admin)
def marketing_analytics(request):
    """Marketing analytics dashboard"""
    # Campaign performance over time
    campaigns = Marketing.objects.filter(is_sent=True).order_by('sent_at')
    
    # Performance metrics
    total_campaigns = campaigns.count()
    total_messages_sent = sum(c.total_sent for c in campaigns)
    total_messages_delivered = sum(c.total_delivered for c in campaigns)
    average_open_rate = sum(c.open_rate for c in campaigns) / total_campaigns if total_campaigns > 0 else 0
    average_click_rate = sum(c.click_rate for c in campaigns) / total_campaigns if total_campaigns > 0 else 0
    
    # Campaigns by type
    campaigns_by_type = Marketing.objects.filter(is_sent=True).values(
        'message_type'
    ).annotate(
        count=Count('id'),
        avg_open_rate=Avg('open_rate'),
        avg_click_rate=Avg('click_rate')
    ).order_by('-count')
    
    # Recent activity
    recent_activity = Marketing.objects.all().order_by('-updated_at')[:10]
    
    context = {
        'total_campaigns': total_campaigns,
        'total_messages_sent': total_messages_sent,
        'total_messages_delivered': total_messages_delivered,
        'average_open_rate': round(average_open_rate, 1),
        'average_click_rate': round(average_click_rate, 1),
        'campaigns_by_type': campaigns_by_type,
        'recent_activity': recent_activity,
    }
    return render(request, 'marketing/analytics.html', context)

@login_required
@user_passes_test(is_admin)
def send_transaction_notification(request):
    """Send transaction notification to user"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            transaction_id = data.get('transaction_id')
            notification_type = data.get('type', 'success')
            
            # Get user and transaction
            user = User.objects.get(id=user_id)
            transaction = EcoCashTransaction.objects.get(id=transaction_id)
            
            # Create message based on type
            if notification_type == 'success':
                message = f"""
🎉 Transaction Successful!

Your deposit of ${transaction.amount} has been processed successfully!

Transaction ID: {transaction.reference_number}
Account: {transaction.deriv_account_number}

Thank you for using Henry Patson!
"""
            elif notification_type == 'failed':
                message = f"""
❌ Transaction Failed!

Your deposit of ${transaction.amount} could not be processed.

Transaction ID: {transaction.reference_number}
Reason: {transaction.failure_reason or 'Unknown error'}

Please contact support for assistance.
"""
            
            # Here you would integrate with your messaging system
            # For WhatsApp, SMS, Email, etc.
            
            # For now, create a marketing record
            campaign = Marketing.objects.create(
                title=f"Transaction Notification - {transaction.reference_number}",
                content=message,
                message_type='transaction_success' if notification_type == 'success' else 'transaction_failed',
                audience_type='specific',
                created_by=request.user,
                is_sent=True,
                sent_at=timezone.now(),
                total_sent=1,
                total_delivered=1
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Notification sent successfully',
                'campaign_id': campaign.id
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)