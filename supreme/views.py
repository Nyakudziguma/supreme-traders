from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q
from django.contrib import messages
from django.db.models.functions import TruncMonth
from decimal import Decimal

@login_required
def dashboard(request):
    if request.user.is_staff:
        # Get filter parameters
        time_filter = request.GET.get('time_filter', 'month')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Base queryset filter
        base_filter = Q()
        
        # Apply date filters
        if date_from:
            try:
                base_filter &= Q(created_at__date__gte=datetime.fromisoformat(date_from).date())
            except:
                pass
        
        if date_to:
            try:
                base_filter &= Q(created_at__date__lte=datetime.fromisoformat(date_to).date())
            except:
                pass
        
        # Calculate time range for quick filters
        today = timezone.now().date()
        if time_filter == 'today':
            base_filter &= Q(created_at__date=today)
            time_label = "Today"
        elif time_filter == 'week':
            start_date = today - timedelta(days=today.weekday())
            base_filter &= Q(created_at__date__gte=start_date)
            time_label = "This Week"
        elif time_filter == 'month':
            base_filter &= Q(created_at__date__year=today.year, created_at__date__month=today.month)
            time_label = "This Month"
        elif time_filter == 'year':
            base_filter &= Q(created_at__date__year=today.year)
            time_label = "This Year"
        else:
            time_label = "All Time"
        
        # Import models
        try:
            from accounts.models import User
            from finance.models import EcoCashTransaction, BillingCycle
            from signals.models import Subscribers
        except ImportError as e:
            # For debugging, return empty context if models not found
            print(f"Model import error: {e}")
            # Return minimal context for template to render
            return render(request, 'dashboard/admin_dashboard.html', {
                'time_filter': time_filter,
                'date_from': date_from,
                'date_to': date_to,
                'time_label': time_label,
                'total_users': 0,
                'new_users': 0,
                'filtered_users': 0,
                'total_deposits': 0,
                'deposit_amount': Decimal('0.00'),
                'deposit_charges': Decimal('0.00'),
                'total_withdrawals': 0,
                'withdrawal_amount': Decimal('0.00'),
                'withdrawal_charges': Decimal('0.00'),
                'total_subscriptions': 0,
                'active_subscriptions': 0,
                'training_subscribers': 0,
                'total_charges': Decimal('0.00'),
                'subscription_revenue': Decimal('0.00'),
                'total_revenue': Decimal('0.00'),
                'total_transactions': 0,
                'completed_transactions': 0,
                'avg_transaction': Decimal('0.00'),
                'success_rate': 0,
                'recent_transactions': [],
                'status_distribution': [],
                'months_data': [],
                'users_data': []
            })
        
        # 1. User Statistics
        total_users = User.objects.count()
        new_users = User.objects.filter(created_at__date=today).count()
        filtered_users = User.objects.filter(base_filter).count()
        
        # 2. Transaction Statistics
        deposits = EcoCashTransaction.objects.filter(
            base_filter & Q(transaction_type='deposit', status='completed')
        )
        withdrawals = EcoCashTransaction.objects.filter(
            base_filter & Q(transaction_type='withdrawal', status='completed')
        )
        
        # Get deposit stats
        deposit_stats = deposits.aggregate(
            count=Count('id'),
            amount=Sum('amount'),
            charges=Sum('charge')
        )
        total_deposits = deposit_stats['count'] or 0
        deposit_amount = deposit_stats['amount'] or Decimal('0.00')
        deposit_charges = deposit_stats['charges'] or Decimal('0.00')
        
        # Get withdrawal stats
        withdrawal_stats = withdrawals.aggregate(
            count=Count('id'),
            amount=Sum('amount'),
            charges=Sum('charge')
        )
        total_withdrawals = withdrawal_stats['count'] or 0
        withdrawal_amount = withdrawal_stats['amount'] or Decimal('0.00')
        withdrawal_charges = withdrawal_stats['charges'] or Decimal('0.00')

        current_billing = BillingCycle.objects.filter(paid=False).last()
        billing_amount_due = float(current_billing.amount_due) if current_billing else 0.00
        billing_transactions_count = current_billing.transactions_count if current_billing else 0

        
        # 3. Subscription Statistics (adjust based on your actual model)
        try:
            total_subscriptions = Subscribers.objects.filter(base_filter).count()
            active_subscriptions = Subscribers.objects.filter(base_filter & Q(active=True)).count()
        except:
            total_subscriptions = 0
            active_subscriptions = 0
        
        # 4. Training subscribers (assuming trainers are a user type)
        training_subscribers = User.objects.filter(
            base_filter & Q(user_type='trainer')
        ).count()
        
        # 5. Revenue Calculation
        transaction_charges = EcoCashTransaction.objects.filter(
            base_filter & Q(status='completed')
        ).aggregate(total=Sum('charge'))['total'] or Decimal('0.00')
        total_charges = transaction_charges
        
        # Subscription revenue (if you have subscription prices)
        try:
            subscription_revenue = Subscribers.objects.filter(
                base_filter & Q(active=True)
            ).aggregate(total=Sum('plan__price'))['total'] or Decimal('0.00')
        except:
            subscription_revenue = Decimal('0.00')
        
        total_revenue = total_charges + subscription_revenue
        
        # 6. Success Rate and Averages
        total_transactions = total_deposits + total_withdrawals
        completed_transactions = EcoCashTransaction.objects.filter(
            base_filter & Q(status='completed')
        ).count()
        
        if total_transactions > 0:
            success_rate = (completed_transactions / total_transactions) * 100
        else:
            success_rate = 0
        
        total_amount = deposit_amount + withdrawal_amount
        if total_transactions > 0:
            avg_transaction = total_amount / Decimal(str(total_transactions))
        else:
            avg_transaction = Decimal('0.00')
        
        # 7. Recent Activity
        recent_transactions = EcoCashTransaction.objects.filter(
            base_filter
        ).select_related('user').order_by('-created_at')[:10]
        
        # 8. Status Distribution
        status_distribution = EcoCashTransaction.objects.filter(
            base_filter
        ).values('status').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        )
        
        # 9. Monthly Trends
        months_data = EcoCashTransaction.objects.filter(
            status='completed',
            created_at__date__gte=today - timedelta(days=180)
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            deposits=Sum('amount', filter=Q(transaction_type='deposit')),
            withdrawals=Sum('amount', filter=Q(transaction_type='withdrawal')),
            charges=Sum('charge')
        ).order_by('month')
        
        # 10. User Growth Trend
        users_data = User.objects.filter(
            created_at__date__gte=today - timedelta(days=180)
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        context = {
            'time_filter': time_filter,
            'date_from': date_from,
            'date_to': date_to,
            'time_label': time_label,
            
            # User statistics
            'total_users': total_users,
            'new_users': new_users,
            'filtered_users': filtered_users,
            
            # Transaction statistics
            'total_deposits': total_deposits,
            'deposit_amount': deposit_amount,
            'deposit_charges': deposit_charges,
            
            'total_withdrawals': total_withdrawals,
            'withdrawal_amount': withdrawal_amount,
            'withdrawal_charges': withdrawal_charges,
            
            # Subscription statistics
            'total_subscriptions': total_subscriptions,
            'active_subscriptions': active_subscriptions,
            'training_subscribers': training_subscribers,
            
            # Revenue statistics
            'total_charges': total_charges,
            'subscription_revenue': subscription_revenue,
            'total_revenue': total_revenue,
            
            # Performance metrics
            'total_transactions': total_transactions,
            'completed_transactions': completed_transactions,
            'avg_transaction': avg_transaction,
            'success_rate': success_rate,
            
            # Recent activity
            'recent_transactions': recent_transactions,
            
            # Status distribution
            'status_distribution': status_distribution,

            'billing_amount_due': billing_amount_due,
            'billing_transactions_count': billing_transactions_count,
            
            # Chart data
            'months_data': list(months_data),
            'users_data': list(users_data),
        }
        
        return render(request, 'dashboard/admin_dashboard.html', context)
    else:
        return redirect('accounts:login')