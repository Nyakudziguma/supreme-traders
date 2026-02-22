from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q
from django.contrib import messages
from django.db.models.functions import TruncMonth
from decimal import Decimal
from django.db.models.functions import TruncMonth, TruncDay


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
            print(f"Model import error: {e}")
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
                'users_data': [],
                'today_weltrade_deposits': 0,
                'today_weltrade_amount': Decimal('0.00'),
                'today_weltrade_charges': Decimal('0.00'),
                'today_deriv_deposits': 0,
                'today_deriv_deposit_amount': Decimal('0.00'),
                'today_deriv_deposit_charges': Decimal('0.00'),
                'today_deriv_withdrawals': 0,
                'today_deriv_withdrawal_amount': Decimal('0.00'),
                'chart_days': [],
                'chart_deposits': [],
                'chart_withdrawals': [],
                'chart_weltrade': [],
                'chart_user_days': [],
                'chart_user_counts': [],
            })
        
        # TODAY'S SUCCESSFUL TRANSACTIONS
        today_filter = Q(created_at__date=today, status='completed')
        
        # Today's successful Weltrade deposits
        weltrade_deposits_today = EcoCashTransaction.objects.filter(
            today_filter & Q(transaction_type='weltrade_deposit')
        )
        weltrade_stats = weltrade_deposits_today.aggregate(
            count=Count('id'),
            amount=Sum('amount'),
            charges=Sum('charge')
        )
        today_weltrade_deposits = weltrade_stats['count'] or 0
        today_weltrade_amount = weltrade_stats['amount'] or Decimal('0.00')
        today_weltrade_charges = weltrade_stats['charges'] or Decimal('0.00')
        
        # Today's successful Deriv deposits
        deriv_deposits_today = EcoCashTransaction.objects.filter(
            today_filter & Q(transaction_type='deposit')
        )
        deriv_deposit_stats = deriv_deposits_today.aggregate(
            count=Count('id'),
            amount=Sum('amount'),
            charges=Sum('charge')
        )
        today_deriv_deposits = deriv_deposit_stats['count'] or 0
        today_deriv_deposit_amount = deriv_deposit_stats['amount'] or Decimal('0.00')
        today_deriv_deposit_charges = deriv_deposit_stats['charges'] or Decimal('0.00')
        
        # Today's successful Deriv withdrawals
        deriv_withdrawals_today = EcoCashTransaction.objects.filter(
            today_filter & Q(transaction_type='withdrawal')
        )
        deriv_withdrawal_stats = deriv_withdrawals_today.aggregate(
            count=Count('id'),
            amount=Sum('amount')
        )
        today_deriv_withdrawals = deriv_withdrawal_stats['count'] or 0
        today_deriv_withdrawal_amount = deriv_withdrawal_stats['amount'] or Decimal('0.00')
        
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
        weltrade_deposits = EcoCashTransaction.objects.filter(
            base_filter & Q(transaction_type='weltrade_deposit', status='completed')
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
        
        # Get Weltrade deposit stats
        weltrade_stats = weltrade_deposits.aggregate(
            count=Count('id'),
            amount=Sum('amount'),
            charges=Sum('charge')
        )
        total_weltrade_deposits = weltrade_stats['count'] or 0
        weltrade_amount = weltrade_stats['amount'] or Decimal('0.00')
        weltrade_charges = weltrade_stats['charges'] or Decimal('0.00')

        current_billing = BillingCycle.objects.filter(paid=False).last()
        billing_amount_due = float(current_billing.amount_due) if current_billing else 0.00
        billing_transactions_count = current_billing.transactions_count if current_billing else 0

        # 3. Subscription Statistics
        try:
            total_subscriptions = Subscribers.objects.filter(base_filter).count()
            active_subscriptions = Subscribers.objects.filter(base_filter & Q(active=True)).count()
        except:
            total_subscriptions = 0
            active_subscriptions = 0
        
        # 4. Training subscribers
        training_subscribers = User.objects.filter(
            base_filter & Q(user_type='trainer')
        ).count()
        
        # 5. Revenue Calculation
        transaction_charges = EcoCashTransaction.objects.filter(
            base_filter & Q(status='completed')
        ).aggregate(total=Sum('charge'))['total'] or Decimal('0.00')
        total_charges = transaction_charges
        
        try:
            subscription_revenue = Subscribers.objects.filter(
                base_filter & Q(active=True)
            ).aggregate(total=Sum('plan__price'))['total'] or Decimal('0.00')
        except:
            subscription_revenue = Decimal('0.00')
        
        total_revenue = total_charges + subscription_revenue
        
        # 6. Success Rate and Averages
        total_transactions = total_deposits + total_withdrawals + total_weltrade_deposits
        completed_transactions = EcoCashTransaction.objects.filter(
            base_filter & Q(status='completed')
        ).count()
        
        if total_transactions > 0:
            success_rate = (completed_transactions / total_transactions) * 100
        else:
            success_rate = 0
        
        total_amount = deposit_amount + withdrawal_amount + weltrade_amount
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
        
        # 9. Daily Trends for Current Month
        first_day_of_month = today.replace(day=1)
        
        # Get daily transaction data for current month
        daily_transactions = EcoCashTransaction.objects.filter(
            status='completed',
            created_at__date__gte=first_day_of_month,
            created_at__date__lte=today
        ).annotate(
            day=TruncDay('created_at')
        ).values('day').annotate(
            deposits=Sum('amount', filter=Q(transaction_type='deposit')),
            withdrawals=Sum('amount', filter=Q(transaction_type='withdrawal')),
            weltrade=Sum('amount', filter=Q(transaction_type='weltrade_deposit')),
        ).order_by('day')

        # Prepare daily chart data
        chart_days = []
        chart_deposits = []
        chart_withdrawals = []
        chart_weltrade = []
        
        # Create a dictionary of existing data
        daily_data = {}
        for item in daily_transactions:
            if item['day']:
                day_str = item['day'].strftime('%Y-%m-%d')
                daily_data[day_str] = {
                    'deposits': float(item['deposits'] or 0),
                    'withdrawals': float(item['withdrawals'] or 0),
                    'weltrade': float(item['weltrade'] or 0)
                }
        
        # Fill in all days of the month
        current_date = first_day_of_month
        while current_date <= today:
            day_str = current_date.strftime('%Y-%m-%d')
            day_display = current_date.strftime('%d %b')
            chart_days.append(day_display)
            
            if day_str in daily_data:
                chart_deposits.append(daily_data[day_str]['deposits'])
                chart_withdrawals.append(daily_data[day_str]['withdrawals'])
                chart_weltrade.append(daily_data[day_str]['weltrade'])
            else:
                chart_deposits.append(0)
                chart_withdrawals.append(0)
                chart_weltrade.append(0)
            
            current_date += timedelta(days=1)
        
        # 10. User Daily Growth for Current Month
        daily_users = User.objects.filter(
            created_at__date__gte=first_day_of_month,
            created_at__date__lte=today
        ).annotate(
            day=TruncDay('created_at')
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')

        # Prepare user daily chart data
        chart_user_days = []
        chart_user_counts = []
        
        # Create dictionary of user data
        user_daily_data = {}
        for item in daily_users:
            if item['day']:
                day_str = item['day'].strftime('%Y-%m-%d')
                user_daily_data[day_str] = item['count']
        
        # Fill in all days of the month
        current_date = first_day_of_month
        while current_date <= today:
            day_str = current_date.strftime('%Y-%m-%d')
            day_display = current_date.strftime('%d %b')
            chart_user_days.append(day_display)
            chart_user_counts.append(user_daily_data.get(day_str, 0))
            current_date += timedelta(days=1)
        
        context = {
            'time_filter': time_filter,
            'date_from': date_from,
            'date_to': date_to,
            'time_label': time_label,
            
            # TODAY'S STATS
            'today_weltrade_deposits': today_weltrade_deposits,
            'today_weltrade_amount': today_weltrade_amount,
            'today_weltrade_charges': today_weltrade_charges,
            'today_deriv_deposits': today_deriv_deposits,
            'today_deriv_deposit_amount': today_deriv_deposit_amount,
            'today_deriv_deposit_charges': today_deriv_deposit_charges,
            'today_deriv_withdrawals': today_deriv_withdrawals,
            'today_deriv_withdrawal_amount': today_deriv_withdrawal_amount,
            
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
            
            'total_weltrade_deposits': total_weltrade_deposits,
            'weltrade_amount': weltrade_amount,
            'weltrade_charges': weltrade_charges,
            
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
            
            # Chart data - Daily for current month
            'chart_days': chart_days,
            'chart_deposits': chart_deposits,
            'chart_withdrawals': chart_withdrawals,
            'chart_weltrade': chart_weltrade,
            'chart_user_days': chart_user_days,
            'chart_user_counts': chart_user_counts,
        }
        
        return render(request, 'dashboard/admin_dashboard.html', context)
    else:
        return redirect('accounts:login')