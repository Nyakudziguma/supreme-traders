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
from decimal import Decimal
import asyncio
import re
from difflib import SequenceMatcher
from django.contrib.auth.decorators import login_required, user_passes_test
from accounts.models import User
from whatsapp.models import ClientVerification
from ecocash.models import CashOutTransaction
from django.views.decorators.http import require_POST
from django.db import transaction
from .forms import CashOutTransactionForm
import random
import string
import json
from datetime import datetime

def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

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
    """Admin view to create and process a new transaction manually"""
    if request.method == 'POST':
        form = AdminTransactionForm(request.POST)
        
        if form.is_valid():
            try:
                # Save the transaction first
                transaction = form.save(commit=False)
                transaction.reference_number = f"DP{datetime.now().strftime('%Y%m%d%H%M%S')}"
                transaction.status = 'pending'
                transaction.save()
                
                # Process the transaction (similar to WhatsApp flow)
                result = process_admin_deposit_transaction(transaction)
                
                if result['success']:
                    messages.success(request, f'Transaction {transaction.reference_number} created and processed successfully!')
                    
                    if result.get('deriv_transaction_id'):
                        transaction.deriv_transaction_id = result['deriv_transaction_id']
                        transaction.status = 'completed'
                        transaction.completed_at = datetime.now()
                        transaction.save()
                    
                    return redirect('finance:admin_transaction_detail', pk=transaction.pk)
                else:
                    # Update transaction status to failed
                    transaction.status = 'failed'
                    transaction.failure_reason = result.get('error', 'Unknown error')
                    transaction.save()
                    
                    messages.error(request, f'Transaction created but processing failed: {result.get("error")}')
                    return render(request, 'finance/admin/transaction_create.html', {'form': form})
                    
            except Exception as e:
                messages.error(request, f'Error creating transaction: {str(e)}')
                return render(request, 'finance/admin/transaction_create.html', {'form': form})
    else:
        form = AdminTransactionForm()
    
    context = {
        'form': form,
    }
    return render(request, 'finance/admin/transaction_create.html', context)


def process_admin_deposit_transaction(transaction):
    """Process deposit transaction similar to WhatsApp flow (for admin)"""
    try:
        # Import DerivPaymentAgent
        from deriv.views import DerivPaymentAgent
        
        # Calculate net amount and charge
        net_amount, charge = calculate_net_amount_and_charge_admin(transaction.amount)
        
        # Update transaction with calculated values
        transaction.amount = net_amount
        transaction.charge = charge
        transaction.save()
        
        # Initialize Deriv agent
        deriv_agent = DerivPaymentAgent()
        
        # Step 1: Fetch recipient details from Deriv
        details_result = asyncio.run(
            deriv_agent.fetch_payment_agent_transfer_details(net_amount, transaction.deriv_account_number)
        )
        
        # Handle error response (WhatsApp URL)
        if isinstance(details_result, str) and details_result.startswith("https://wa.me/"):
            return {
                'success': False,
                'error': "Could not fetch recipient details from Deriv. Please verify the account number."
            }
        
        # Check if we got valid details
        if isinstance(details_result, dict) and 'client_to_full_name' in details_result:
            deriv_name = details_result['client_to_full_name']
            local_name = transaction.ecocash_name
            
            # Normalize names for comparison
            deriv_tokens = normalize_name_admin(deriv_name)
            local_tokens = normalize_name_admin(local_name)
            
            # Step 2: Check if names match
            if deriv_tokens & local_tokens or names_match_admin(deriv_name, local_name):
                # ✅ Names match, process transfer
                return process_admin_transfer(
                    deriv_agent, net_amount, transaction, 
                    details_result, deriv_name
                )
            else:
                # ❌ Name mismatch, try client verification
                return handle_admin_name_mismatch(
                    deriv_agent, net_amount, transaction,
                    details_result, deriv_name, local_name
                )
        else:
            return {
                'success': False,
                'error': "Invalid response from Deriv. Please try again."
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f"Processing error: {str(e)}"
        }


def calculate_net_amount_and_charge_admin(total_amount):
    """Calculate net amount and charge for admin transactions"""
    try:
        from finance.models import TransactionCharge
        
        # First, check which charge range would apply
        charge_table = TransactionCharge.objects.filter(
            is_active=True
        ).order_by('min_amount')
        
        for charge_config in charge_table:
            if charge_config.is_percentage:
                percentage_decimal = charge_config.percentage_rate / Decimal('100')
                net_amount = (total_amount - charge_config.additional_fee) / (Decimal('1') + percentage_decimal)
                
                if charge_config.min_amount <= net_amount <= charge_config.max_amount:
                    charge = total_amount - net_amount
                    return net_amount.quantize(Decimal('0.01')), charge.quantize(Decimal('0.01'))
            else:
                net_amount = total_amount - charge_config.fixed_charge
                
                # Check if net_amount falls in this range
                if charge_config.min_amount <= net_amount <= charge_config.max_amount:
                    charge = charge_config.fixed_charge
                    return net_amount.quantize(Decimal('0.01')), charge.quantize(Decimal('0.01'))
        
        # Fallback: use 10% + 0.9 as default
        net_amount = (total_amount - Decimal('0.90')) / Decimal('1.10')
        charge = total_amount - net_amount
        return net_amount.quantize(Decimal('0.01')), charge.quantize(Decimal('0.01'))
        
    except Exception as e:
        print(f"Error calculating net amount: {e}")
        # Default fallback
        net_amount = (total_amount - Decimal('0.90')) / Decimal('1.10')
        charge = total_amount - net_amount
        return net_amount.quantize(Decimal('0.01')), charge.quantize(Decimal('0.01'))


def process_admin_transfer(deriv_agent, net_amount, transaction, details_result, deriv_name):
    """Process the actual transfer for admin"""
    try:
        transfer_result = asyncio.run(
            deriv_agent.create_payment_agent_transfer(net_amount, transaction.deriv_account_number)
        )
        
        if isinstance(transfer_result, dict) and 'transaction_id' in transfer_result:
            # ✅ Transfer successful
            transaction.deriv_transaction_id = transfer_result.get('transaction_id')
            transaction.status = 'completed'
            transaction.completed_at = datetime.now()
            transaction.notes = f"Deposit completed successfully via admin. Deriv name: {deriv_name}"
            transaction.save()
            
            return {
                'success': True,
                'deriv_transaction_id': transfer_result.get('transaction_id'),
                'message': f"Transfer successful! Deriv Transaction ID: {transfer_result.get('transaction_id')}"
            }
        else:
            # ❌ Transfer failed
            error_msg = parse_deriv_error(transfer_result)
            return {
                'success': False,
                'error': error_msg
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f"Transfer error: {str(e)}"
        }


def handle_admin_name_mismatch(deriv_agent, net_amount, transaction, details_result, deriv_name, local_name):
    """Handle name mismatch for admin transactions"""
    from whatsapp.models import ClientVerification
    
    # Check for client verification
    client_verification = ClientVerification.objects.filter(ecocash_number=transaction.ecocash_number,verified=True).first()
    
    if client_verification:
        verified_name = client_verification.name
        if names_match_admin(verified_name, local_name):
            # ✅ Verified name matches, process transfer
            return process_admin_transfer(
                deriv_agent, net_amount, transaction,
                details_result, deriv_name
            )
    
    # Still no match
    return {
        'success': False,
        'error': f"Name verification failed. Deriv name: {deriv_name}, EcoCash name: {local_name}"
    }


def normalize_name_admin(name: str) -> set:
    """Normalize name for admin comparison"""
    if not name:
        return set()

    # Remove titles
    name = re.sub(r"^(mr|mrs|ms|miss|dr)\.?\s+", "", name, flags=re.IGNORECASE)

    # Split into parts
    tokens = re.split(r"\s+", name.strip())
    return set(token.lower().strip(".") for token in tokens if token)


def names_match_admin(name1: str, name2: str) -> bool:
    """Check if names match for admin"""
    n1, n2 = normalize_name_admin(name1), normalize_name_admin(name2)
    ratio = SequenceMatcher(None, n1, n2).ratio()
    return ratio >= 0.75


def parse_deriv_error(transfer_result):
    """Parse Deriv API error messages"""
    if isinstance(transfer_result, str):
        if "client's resident country is not within your portfolio" in transfer_result:
            return "Invalid CR number. Please ensure it's a Zimbabwean Deriv account."
        elif "https://wa.me/" in transfer_result:
            return "Deriv API error. Please contact support."
    
    return "Transfer failed. Please try again or contact support."

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
        'total_charges': (total_deposits['charges'] or 0),
        'recent_transactions': recent_transactions,
        'status_counts': status_counts,
    }
    
    return render(request, 'finance/admin/dashboard.html', context)

# finance/views.py

@admin_required
def api_calculate_charge(request):
    """API endpoint to calculate charge for an amount"""
    amount = request.GET.get('amount')
    
    if not amount:
        return JsonResponse({'error': 'Amount required'}, status=400)
    
    try:
        amount_decimal = Decimal(amount)
        net_amount, charge = calculate_net_amount_and_charge_admin(amount_decimal)
        
        return JsonResponse({
            'net_amount': str(net_amount),
            'charge': str(charge)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@admin_required
def api_verify_ecocash(request):
    """API endpoint to verify EcoCash number"""
    number = request.GET.get('number')
    
    if not number:
        return JsonResponse({'error': 'Number required'}, status=400)
    
    try:
        # Check if number exists in ClientVerification
        from whatsapp.models import ClientVerification
        from ecocash.models import CashOutTransaction
        
        # Normalize phone number
        normalized = number.lstrip('0')
        if normalized.startswith('263'):
            normalized = normalized[3:]
        
        # Check ClientVerification
        verification = ClientVerification.objects.filter(
            ecocash_number__in=[
                number,
                normalized,
                '0' + normalized,
                '263' + normalized,
                '+263' + normalized
            ],
            verified=True
        ).first()
        
        if verification:
            return JsonResponse({
                'verified': True,
                'message': 'Verified client',
                'name': verification.name
            })
        
        # Check recent CashOutTransactions
        cashout = CashOutTransaction.objects.filter(
            phone__in=[
                number,
                normalized,
                '0' + normalized,
                '263' + normalized,
                '+263' + normalized
            ]
        ).order_by('-created_at').first()
        
        if cashout:
            return JsonResponse({
                'verified': True,
                'message': 'Found in transaction history',
                'name': cashout.name
            })
        
        return JsonResponse({
            'verified': False,
            'message': 'Number not found in verification records'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    


@login_required
@user_passes_test(is_admin)
def client_verification_list(request):
    """List all client verification requests"""
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    verified_by_filter = request.GET.get('verified_by', '')
    
    clients = ClientVerification.objects.all().order_by('-created_at')
    
    # Apply filters
    if search_query:
        clients = clients.filter(
            Q(name__icontains=search_query) |
            Q(ecocash_number__icontains=search_query)
        )
    
    if status_filter != 'all':
        if status_filter == 'verified':
            clients = clients.filter(verified=True)
        elif status_filter == 'unverified':
            clients = clients.filter(verified=False)
    
    if verified_by_filter:
        clients = clients.filter(verified_by__username__icontains=verified_by_filter)
    
    # Pagination
    paginator = Paginator(clients, 20)  # 20 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all admins for filter
    admins = User.objects.filter(is_staff=True, user_type='admin')
    
    context = {
        'clients': page_obj,
        'admins': admins,
        'total_count': clients.count(),
        'verified_count': clients.filter(verified=True).count(),
        'unverified_count': clients.filter(verified=False).count(),
        'search_query': search_query,
        'status_filter': status_filter,
        'verified_by_filter': verified_by_filter,
    }
    return render(request, 'finance/admin/client_verification/list.html', context)

@login_required
@user_passes_test(is_admin)
def client_verification_detail(request, pk):
    """View client verification details"""
    client = get_object_or_404(ClientVerification, pk=pk)
    
    # Get related transactions
    related_transactions = EcoCashTransaction.objects.filter(
        ecocash_number=client.ecocash_number
    ).order_by('-created_at')[:10]
    
    context = {
        'client': client,
        'related_transactions': related_transactions,
    }
    return render(request, 'finance/admin/client_verification/detail.html', context)

@login_required
@user_passes_test(is_admin)
def client_verification_create(request):
    """Create new client verification manually"""
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name')
            ecocash_number = request.POST.get('ecocash_number')
            
            # Normalize phone number
            normalized_phone = ecocash_number.lstrip('0')
            if not normalized_phone.startswith('263'):
                normalized_phone = '263' + normalized_phone
            
            # Check if client already exists
            existing_client = ClientVerification.objects.filter(
                ecocash_number__in=[
                    ecocash_number,
                    normalized_phone,
                    '0' + normalized_phone[3:],
                    '263' + normalized_phone[3:] if len(normalized_phone) > 9 else normalized_phone
                ]
            ).first()
            
            if existing_client:
                messages.warning(request, f'Client with EcoCash number {ecocash_number} already exists')
                return redirect('finance:client_verification_list')
            
            # Create new client
            client = ClientVerification.objects.create(
                name=name,
                ecocash_number=normalized_phone
            )
            
            # Handle file uploads if provided
            if 'national_id_image' in request.FILES:
                client.national_id_image = request.FILES['national_id_image']
            
            if 'selfie_with_id' in request.FILES:
                client.selfie_with_id = request.FILES['selfie_with_id']
            
            client.save()
            
            messages.success(request, f'Client {name} has been added successfully')
            return redirect('finance:client_verification_detail', pk=client.pk)
            
        except Exception as e:
            messages.error(request, f'Error creating client: {str(e)}')
            return redirect('finance:client_verification_list')
    
    return redirect('finance:client_verification_list')

@login_required
@user_passes_test(is_admin)
def client_verification_verify(request, pk):
    from whatsapp.services import WhatsAppService
    service=WhatsAppService()

    """Approve a previously rejected client."""
    client = get_object_or_404(ClientVerification, pk=pk)
    
    try:
        client.rejected = False
        client.verified = True
        client.rejection_reason = None
        client.verified_by = request.user
        client.verified_at = timezone.now()
        client.save()

        service.send_message(client.trader.phone_number, "Good news, your KYCs have been veried. You can now make weltrade deposits!")      
        messages.success(request, f'Client {client.name} approved and verified.')
    except Exception as e:
        messages.error(request, f'Error approving client: {str(e)}')
    
    return redirect('finance:client_verification_detail', pk=pk)

@login_required
@user_passes_test(is_admin)
def client_verification_unverify(request, pk):
    """Unverify a client"""
    if request.method == 'POST':
        try:
            client = get_object_or_404(ClientVerification, pk=pk)
            
            if not client.verified:
                messages.warning(request, f'Client {client.name} is already unverified')
            else:
                client.verified = False
                client.verified_by = None
                client.verified_at = None
                client.save()
                
                messages.success(request, f'Client {client.name} has been unverified')
            
            return redirect('finance:client_verification_detail', pk=client.pk)
            
        except Exception as e:
            messages.error(request, f'Error unverifying client: {str(e)}')
    
    return redirect('finance:client_verification_list')

@login_required
@user_passes_test(is_admin)
def client_verification_update(request, pk):
    """Update client information"""
    if request.method == 'POST':
        try:
            client = get_object_or_404(ClientVerification, pk=pk)
            
            name = request.POST.get('name')
            ecocash_number = request.POST.get('ecocash_number')
            
            # Normalize phone number
            normalized_phone = ecocash_number.lstrip('0')
            if not normalized_phone.startswith('263'):
                normalized_phone = '263' + normalized_phone
            
            # Check if phone number is already taken by another client
            existing_client = ClientVerification.objects.filter(
                ecocash_number=normalized_phone
            ).exclude(pk=client.pk).first()
            
            if existing_client:
                messages.warning(request, f'EcoCash number {ecocash_number} is already registered to {existing_client.name}')
                return redirect('finance:client_verification_detail', pk=client.pk)
            
            # Update client
            client.name = name
            client.ecocash_number = normalized_phone
            
            # Handle file uploads
            if 'national_id_image' in request.FILES:
                client.national_id_image = request.FILES['national_id_image']
            
            if 'selfie_with_id' in request.FILES:
                client.selfie_with_id = request.FILES['selfie_with_id']
            
            client.save()
            
            messages.success(request, f'Client information updated successfully')
            return redirect('finance:client_verification_detail', pk=client.pk)
            
        except Exception as e:
            messages.error(request, f'Error updating client: {str(e)}')
    
    return redirect('finance:client_verification_list')

@login_required
@user_passes_test(is_admin)
def client_verification_delete(request, pk):
    """Delete a client verification"""
    if request.method == 'POST':
        try:
            client = get_object_or_404(ClientVerification, pk=pk)
            client_name = client.name
            
            # Check if client has related transactions
            related_transactions = EcoCashTransaction.objects.filter(
                ecocash_number=client.ecocash_number
            ).count()
            
            if related_transactions > 0:
                messages.error(request, f'Cannot delete {client_name} because they have {related_transactions} transaction(s). Unverify them instead.')
                return redirect('finance:client_verification_detail', pk=client.pk)
            
            client.delete()
            messages.success(request, f'Client {client_name} has been deleted successfully')
            
        except Exception as e:
            messages.error(request, f'Error deleting client: {str(e)}')
    
    return redirect('finance:client_verification_list')

@login_required
@user_passes_test(is_admin)
def client_verification_bulk_action(request):
    """Handle bulk actions for clients"""
    if request.method == 'POST':
        action = request.POST.get('action')
        client_ids = request.POST.getlist('client_ids')
        
        if not client_ids:
            messages.warning(request, 'Please select at least one client')
            return redirect('finance:client_verification_list')
        
        clients = ClientVerification.objects.filter(id__in=client_ids)
        
        if action == 'verify':
            updated_count = clients.filter(verified=False).update(
                verified=True,
                verified_by=request.user,
                verified_at=datetime.now()
            )
            messages.success(request, f'{updated_count} client(s) verified successfully')
            
        elif action == 'unverify':
            updated_count = clients.filter(verified=True).update(
                verified=False,
                verified_by=None,
                verified_at=None
            )
            messages.success(request, f'{updated_count} client(s) unverified successfully')
            
        elif action == 'delete':
            # Only delete clients without transactions
            deletable_clients = []
            for client in clients:
                transaction_count = EcoCashTransaction.objects.filter(
                    ecocash_number=client.ecocash_number
                ).count()
                if transaction_count == 0:
                    deletable_clients.append(client.id)
                else:
                    messages.warning(request, f'Skipped {client.name} (has {transaction_count} transaction(s))')
            
            if deletable_clients:
                deleted_count, _ = ClientVerification.objects.filter(id__in=deletable_clients).delete()
                messages.success(request, f'{deleted_count} client(s) deleted successfully')
        
        return redirect('finance:client_verification_list')
    
    return redirect('finance:client_verification_list')

# finance/views/client_verification_views.py
@login_required
@user_passes_test(is_admin)
@require_POST
def client_verification_reject(request, pk):
    from whatsapp.services import WhatsAppService
    service=WhatsAppService()

    """Reject client verification."""
    client = get_object_or_404(ClientVerification, pk=pk)
    rejection_reason = request.POST.get('rejection_reason', '').strip()
    
    if not rejection_reason:
        messages.error(request, 'Rejection reason is required.')
        return redirect('finance:client_verification_detail', pk=pk)
    
    try:
        client.rejected = True
        client.verified = False
        client.rejection_reason = rejection_reason
        client.verified_by = request.user
        client.verified_at = timezone.now()
        client.save()
        service.send_message(client.trader.phone_number, f"Your KYCs have been rejected, {rejection_reason}")
        
        messages.success(request, f'Client {client.name} verification rejected.')
    except Exception as e:
        messages.error(request, f'Error rejecting verification: {str(e)}')
    
    return redirect('finance:client_verification_detail', pk=pk)

@login_required
@user_passes_test(is_admin)
@require_POST
def client_verification_approve(request, pk):
    from whatsapp.services import WhatsAppService
    service=WhatsAppService()

    """Approve a previously rejected client."""
    client = get_object_or_404(ClientVerification, pk=pk)
    
    try:
        client.rejected = False
        client.verified = True
        client.rejection_reason = None
        client.verified_by = request.user
        client.verified_at = timezone.now()
        client.save()

        service.send_message(client.trader.phone_number, "Good news, your KYCs have been veried. You can now make weltrade deposits!")      
        messages.success(request, f'Client {client.name} approved and verified.')
    except Exception as e:
        messages.error(request, f'Error approving client: {str(e)}')
    
    return redirect('finance:client_verification_detail', pk=pk)

@login_required
@user_passes_test(is_admin)
def client_verification_update(request, pk):
    """Update client verification information."""
    client = get_object_or_404(ClientVerification, pk=pk)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        ecocash_number = request.POST.get('ecocash_number', '').strip()
        crypto_wallet_address = request.POST.get('crypto_wallet_address', '').strip()
        
        if not name or not ecocash_number:
            messages.error(request, 'Name and EcoCash number are required.')
            return redirect('finance:client_verification_detail', pk=pk)
        
        try:
            client.name = name
            client.ecocash_number = ecocash_number
            client.crypto_wallet_address = crypto_wallet_address or None
            
            # Handle file uploads
            if 'national_id_image' in request.FILES:
                client.national_id_image = request.FILES['national_id_image']
            
            if 'selfie_with_id' in request.FILES:
                client.selfie_with_id = request.FILES['selfie_with_id']
            
            client.save()
            messages.success(request, f'Client {client.name} updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating client: {str(e)}')
        
        return redirect('finance:client_verification_detail', pk=pk)
    
    return redirect('finance:client_verification_detail', pk=pk)

@login_required
@user_passes_test(is_admin)
def verify_ecocash_api(request):
    """API endpoint to verify EcoCash number"""
    ecocash_number = request.GET.get('number')
    
    if not ecocash_number:
        return JsonResponse({'error': 'EcoCash number required'}, status=400)
    
    try:
        # Normalize phone number
        normalized = ecocash_number.lstrip('0')
        if not normalized.startswith('263'):
            normalized = '263' + normalized
        
        # Check ClientVerification
        client = ClientVerification.objects.filter(
            ecocash_number=normalized
        ).first()
        
        if client:
            return JsonResponse({
                'exists': True,
                'verified': client.verified,
                'name': client.name,
                'client_id': client.id,
                'message': f'Client found: {client.name} ({client.status})'
            })
        
        return JsonResponse({
            'exists': False,
            'message': 'EcoCash number not found in client verification database'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    

def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

@login_required
@user_passes_test(is_admin)
def cashout_transaction_list(request):
    """List all cashout transactions"""
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    
    # Get all transactions ordered by most recent
    transactions = CashOutTransaction.objects.all().order_by('-timestamp')
    
    # Apply search filter
    if search_query:
        transactions = transactions.filter(
            Q(txn_id__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(body__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter != 'all':
        if status_filter == 'pending':
            transactions = transactions.filter(completed=False, flagged=False)
        elif status_filter == 'completed':
            transactions = transactions.filter(completed=True)
        elif status_filter == 'flagged':
            transactions = transactions.filter(flagged=True)
    
    # Calculate stats
    total_count = transactions.count()
    pending_count = transactions.filter(completed=False, flagged=False).count()
    completed_count = transactions.filter(completed=True).count()
    flagged_count = transactions.filter(flagged=True).count()
    
    # Pagination
    paginator = Paginator(transactions, 20)  # 20 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'transactions': page_obj,
        'total_count': total_count,
        'pending_count': pending_count,
        'completed_count': completed_count,
        'flagged_count': flagged_count,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'finance/admin/cashout_transactions/list.html', context)

@login_required
@user_passes_test(is_admin)
def cashout_transaction_mark_completed(request, pk):
    """Mark a cashout transaction as completed"""
    if request.method == 'POST':
        try:
            transaction = get_object_or_404(CashOutTransaction, pk=pk)
            
            if transaction.completed:
                messages.warning(request, f'Transaction {transaction.txn_id} is already marked as completed')
            else:
                transaction.completed = True
                transaction.save()
                
                messages.success(request, f'Transaction {transaction.txn_id} has been marked as completed')
            
            return redirect('finance:cashout_transaction_list')
            
        except Exception as e:
            messages.error(request, f'Error marking transaction as completed: {str(e)}')
    
    return redirect('finance:cashout_transaction_list')

@login_required
@user_passes_test(is_admin)
def cashout_transaction_bulk_complete(request):
    """Mark multiple cashout transactions as completed"""
    if request.method == 'POST':
        try:
            transaction_ids = request.POST.getlist('transaction_ids')
            
            if not transaction_ids:
                messages.warning(request, 'Please select at least one transaction')
                return redirect('finance:cashout_transaction_list')
            
            # Get pending transactions from the selected IDs
            transactions = CashOutTransaction.objects.filter(
                id__in=transaction_ids,
                completed=False
            )
            
            count = transactions.count()
            
            if count > 0:
                transactions.update(completed=True)
                messages.success(request, f'{count} transaction(s) marked as completed')
            else:
                messages.warning(request, 'No pending transactions selected')
            
            return redirect('finance:cashout_transaction_list')
            
        except Exception as e:
            messages.error(request, f'Error completing transactions: {str(e)}')
    
    return redirect('finance:cashout_transaction_list')

@login_required
@user_passes_test(is_admin)
def cashout_transaction_api(request):
    """API endpoint to get transaction details"""
    transaction_id = request.GET.get('id')
    
    if not transaction_id:
        return JsonResponse({'error': 'Transaction ID required'}, status=400)
    
    try:
        transaction = CashOutTransaction.objects.get(pk=transaction_id)
        
        data = {
            'id': transaction.id,
            'txn_id': transaction.txn_id,
            'amount': str(transaction.amount),
            'name': transaction.name,
            'phone': transaction.phone,
            'completed': transaction.completed,
            'flagged': transaction.flagged,
            'fradulent': transaction.fradulent,
            'low_limit': transaction.low_limit,
            'verification_code': transaction.verification_code,
            'timestamp': transaction.timestamp.isoformat(),
            'prev_bal': str(transaction.prev_bal),
            'new_bal': str(transaction.new_bal),
            'flag_reason': transaction.flag_reason,
            'flagged_by': transaction.flagged_by,
            'body': transaction.body,
            'trader': transaction.trader.email if transaction.trader else None,
        }
        
        return JsonResponse(data)
        
    except CashOutTransaction.DoesNotExist:
        return JsonResponse({'error': 'Transaction not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
# views.py - Update the create views

@login_required
@user_passes_test(is_admin)
def cashout_transaction_create(request):
    """Create a new cashout transaction"""
    if request.method == 'POST':
        form = CashOutTransactionForm(request.POST)
        if form.is_valid():
            try:
                # Generate a unique transaction ID if not provided
                txn_id = form.cleaned_data.get('txn_id')
                if not txn_id:
                    txn_id = f"CASHOUT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"
                
                # Check if transaction ID already exists
                if CashOutTransaction.objects.filter(txn_id=txn_id).exists():
                    txn_id = f"{txn_id}-{random.randint(100, 999)}"
                
                # Create the transaction
                cashout_transaction = form.save(commit=False)
                cashout_transaction.txn_id = txn_id
                
                # Generate verification code if not provided
                if not cashout_transaction.verification_code:
                    cashout_transaction.verification_code = ''.join(random.choices(string.digits, k=6))
                
                cashout_transaction.save()
                
                messages.success(request, f'Cashout transaction created successfully! TXN ID: {txn_id}')
                return redirect('finance:cashout_transaction_list')
                
            except Exception as e:
                messages.error(request, f'Error creating transaction: {str(e)}')
        else:
            # Pass form errors to template
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CashOutTransactionForm()
    
    context = {
        'form': form,
    }
    return render(request, 'finance/admin/cashout_transactions/create.html', context)
