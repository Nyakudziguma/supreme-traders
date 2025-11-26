# finance/views_admin.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from .models import EcoCashTransaction, TransactionReceipt, TransactionCharge
from .forms import AdminTransactionForm, TransactionChargeForm

def admin_required(view_func):
    """Decorator to ensure user is admin staff"""
    decorated_view_func = user_passes_test(
        lambda u: u.is_active and u.is_staff and u.user_type == 'admin',
        login_url='accounts:login'
    )(view_func)
    return decorated_view_func

@admin_required
def admin_transaction_list(request):
    """Admin view to list all transactions with filtering"""
    # Get filter parameters
    status = request.GET.get('status', '')
    transaction_type = request.GET.get('type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    # Start with all transactions
    transactions = EcoCashTransaction.objects.all().select_related('user')
    
    # Apply filters
    if status:
        transactions = transactions.filter(status=status)
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            transactions = transactions.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            transactions = transactions.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass
    if search:
        transactions = transactions.filter(
            Q(reference_number__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__phone_number__icontains=search) |
            Q(ecocash_number__icontains=search) |
            Q(deriv_account_number__icontains=search) |
            Q(ecocash_reference__icontains=search)
        )
    
    # Order by latest first
    transactions = transactions.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(transactions, 50)  # 50 transactions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_count = transactions.count()
    pending_count = EcoCashTransaction.objects.filter(status__in=['pending', 'awaiting_pop']).count()
    today_count = EcoCashTransaction.objects.filter(created_at__date=timezone.now().date()).count()
    
    # Total amounts by status
    stats = transactions.aggregate(
        total_amount=Sum('amount'),
        total_charges=Sum('charge')
    )
    
    context = {
        'page_obj': page_obj,
        'total_count': total_count,
        'pending_count': pending_count,
        'today_count': today_count,
        'total_amount': stats['total_amount'] or 0,
        'total_charges': stats['total_charges'] or 0,
        'filter_status': status,
        'filter_type': transaction_type,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
        'filter_search': search,
    }
    
    return render(request, 'finance/admin/transaction_list.html', context)

@admin_required
def admin_transaction_detail(request, pk):
    """Admin view for transaction details"""
    transaction = get_object_or_404(EcoCashTransaction.objects.select_related('user'), pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_status':
            new_status = request.POST.get('status')
            notes = request.POST.get('admin_notes', '')
            
            if new_status in dict(EcoCashTransaction.STATUS_CHOICES):
                transaction.status = new_status
                if notes:
                    transaction.admin_notes = notes
                
                # Handle completed status
                if new_status == 'completed' and not transaction.processed_at:
                    transaction.processed_at = timezone.now()
                    
                    # Set transaction IDs based on type
                    if transaction.transaction_type == 'deposit':
                        transaction.deriv_transaction_id = request.POST.get('deriv_transaction_id', '')
                    else:  # withdrawal
                        transaction.ecocash_transaction_id = request.POST.get('ecocash_transaction_id', '')
                
                transaction.save()
                messages.success(request, f'Transaction status updated to {new_status}')
            
        elif action == 'add_note':
            notes = request.POST.get('admin_notes', '')
            transaction.admin_notes = notes
            transaction.save()
            messages.success(request, 'Admin notes updated')
        
        return redirect('finance:admin_transaction_detail', pk=transaction.pk)
    
    context = {
        'transaction': transaction,
        'receipt': getattr(transaction, 'receipt', None),
    }
    return render(request, 'finance/admin/transaction_detail.html', context)

@admin_required
def admin_transaction_create(request):
    """Admin view to create a new transaction"""
    if request.method == 'POST':
        form = AdminTransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.save()
            messages.success(request, f'Transaction {transaction.reference_number} created successfully')
            return redirect('finance:admin_transaction_detail', pk=transaction.pk)
    else:
        form = AdminTransactionForm()
    
    context = {
        'form': form,
    }
    return render(request, 'finance/admin/transaction_create.html', context)

@admin_required
def admin_verify_receipt(request, pk):
    """Admin view to verify transaction receipt"""
    receipt = get_object_or_404(TransactionReceipt, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'verify':
            receipt.verified = True
            receipt.verified_by = request.user
            receipt.verified_at = timezone.now()
            receipt.verification_notes = request.POST.get('verification_notes', '')
            receipt.save()
            
            # Update transaction status if it's a deposit
            if receipt.transaction.transaction_type == 'deposit':
                receipt.transaction.status = 'processing'
                receipt.transaction.save()
            
            messages.success(request, 'Receipt verified successfully')
        
        elif action == 'reject':
            receipt.verified = False
            receipt.verification_notes = request.POST.get('verification_notes', '')
            receipt.save()
            messages.warning(request, 'Receipt verification rejected')
        
        return redirect('finance:admin_transaction_detail', pk=receipt.transaction.pk)
    
    context = {
        'receipt': receipt,
    }
    return render(request, 'finance/admin/verify_receipt.html', context)

@admin_required
def admin_charges_management(request):
    """Admin view to manage transaction charges"""
    charges = TransactionCharge.objects.all().order_by('min_amount')
    
    if request.method == 'POST':
        form = TransactionChargeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Charge added successfully')
            return redirect('finance:admin_charges_management')
    else:
        form = TransactionChargeForm()
    
    context = {
        'charges': charges,
        'form': form,
    }
    return render(request, 'finance/admin/charges_management.html', context)

@admin_required
def admin_edit_charge(request, pk):
    """Admin view to edit a charge"""
    charge = get_object_or_404(TransactionCharge, pk=pk)
    
    if request.method == 'POST':
        form = TransactionChargeForm(request.POST, instance=charge)
        if form.is_valid():
            form.save()
            messages.success(request, 'Charge updated successfully')
            return redirect('finance:admin_charges_management')
    else:
        form = TransactionChargeForm(instance=charge)
    
    context = {
        'charge': charge,
        'form': form,
    }
    return render(request, 'finance/admin/edit_charge.html', context)

@admin_required
def admin_toggle_charge(request, pk):
    """Toggle charge active status"""
    charge = get_object_or_404(TransactionCharge, pk=pk)
    charge.is_active = not charge.is_active
    charge.save()
    
    status = "activated" if charge.is_active else "deactivated"
    messages.success(request, f'Charge {status} successfully')
    return redirect('finance:admin_charges_management')

@admin_required
def admin_dashboard(request):
    """Admin finance dashboard"""
    # Date ranges
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Statistics
    total_transactions = EcoCashTransaction.objects.count()
    pending_transactions = EcoCashTransaction.objects.filter(status__in=['pending', 'awaiting_pop']).count()
    
    # Amount totals
    total_deposits = EcoCashTransaction.objects.filter(transaction_type='deposit').aggregate(
        total=Sum('amount'), charges=Sum('charge')
    )
    total_withdrawals = EcoCashTransaction.objects.filter(transaction_type='withdrawal').aggregate(
        total=Sum('amount'), charges=Sum('charge')
    )
    
    # Recent transactions
    recent_transactions = EcoCashTransaction.objects.select_related('user').order_by('-created_at')[:10]
    
    # Status counts
    status_counts = EcoCashTransaction.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    context = {
        'total_transactions': total_transactions,
        'pending_transactions': pending_transactions,
        'total_deposits': total_deposits['total'] or 0,
        'total_withdrawals': total_withdrawals['total'] or 0,
        'total_charges': (total_deposits['charges'] or 0) + (total_withdrawals['charges'] or 0),
        'recent_transactions': recent_transactions,
        'status_counts': status_counts,
    }
    
    return render(request, 'finance/admin/dashboard.html', context)