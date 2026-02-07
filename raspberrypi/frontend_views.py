# econet/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime, timedelta
import uuid
import random
from django.utils import timezone
import requests
from requests.auth import HTTPBasicAuth
from django.db import models
from django.conf import settings
from .models import IncomingMessage, IncomingCall, OutgoingMessage, EcocashTransfers, TransactionOTP
from .forms import MoneyTransferForm
from whatsapp.services import WhatsAppService
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q


service = WhatsAppService()

# Get API credentials from settings
ECO_ORIGINATOR = settings.ECO_ORIGINATOR
ECO_DESTINATION = settings.ECO_DESTINATION
ECO_USERNAME = settings.ECO_USERNAME
ECO_PASSWORD = settings.ECO_PASSWORD
ECO_API_URL = settings.ECO_API_URL

@login_required
def message_dashboard(request):
    """econet Dashboard"""
    # Get recent data
    recent_messages = IncomingMessage.objects.all().order_by('-received_at')[:10]
    recent_calls = IncomingCall.objects.all().order_by('-call_time')[:10]
    
    # Get user's recent transfers
    recent_transfers = EcocashTransfers.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    # Stats
    total_transfers = EcocashTransfers.objects.filter(user=request.user).count()
    successful_transfers = EcocashTransfers.objects.filter(
        user=request.user, 
        status="Successful"
    ).count()
    total_amount = EcocashTransfers.objects.filter(
        user=request.user, 
        status="Successful"
    ).aggregate(models.Sum('amount'))['amount__sum'] or 0
    
    context = {
        'recent_messages': recent_messages,
        'recent_calls': recent_calls,
        'recent_transfers': recent_transfers,
        'total_transfers': total_transfers,
        'successful_transfers': successful_transfers,
        'total_amount': total_amount,
        'page_title': 'econet Dashboard',
    }
    return render(request, 'econet/dashboard.html', context)

@login_required
def econet_messages(request):
    """View all messages with pagination"""
    # Get all messages, ordered by most recent first
    messages_list = IncomingMessage.objects.all().order_by('-received_at')
    
    # Handle search
    search_query = request.GET.get('search', '')
    if search_query:
        messages_list = messages_list.filter(
            Q(sender_id__icontains=search_query) |
            Q(message_body__icontains=search_query)
        )
    
    # Handle filter
    filter_query = request.GET.get('filter', 'all')
    if filter_query == 'today':
        today = timezone.now().date()
        messages_list = messages_list.filter(received_at__date=today)
    elif filter_query == 'week':
        week_ago = timezone.now() - timedelta(days=7)
        messages_list = messages_list.filter(received_at__gte=week_ago)
    
    # Pagination
    paginator = Paginator(messages_list, 20)  # Show 20 messages per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate message stats
    total_messages = messages_list.count()
    today_messages = messages_list.filter(received_at__date=timezone.now().date()).count()
    week_messages = messages_list.filter(received_at__gte=timezone.now() - timedelta(days=7)).count()
    
    context = {
        'econet_messages': page_obj,
        'page_title': 'Messages',
        'total_messages': total_messages,
        'today_messages': today_messages,
        'week_messages': week_messages,
        'search_query': search_query,
        'filter_query': filter_query,
    }
    return render(request, 'econet/messages.html', context)

@login_required
def econet_calls(request):
    """View call history"""
    calls = IncomingCall.objects.all().order_by('-call_time')
    
    context = {
        'calls': calls,
        'page_title': 'Call History',
    }
    return render(request, 'econet/calls.html', context)

@login_required
def money_transfer(request):
    """Money transfer form"""
    if request.method == 'POST':
        form = MoneyTransferForm(request.POST)
        if form.is_valid():
            # Create pending transaction
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.status = "Pending"
            transaction.save()
            
            # Generate OTP
            otp = str(random.randint(100000, 999999))
            
            # Save OTP
            TransactionOTP.objects.create(
                user=request.user,
                otp_code=otp,
                phone_number=transaction.ecocash_number,
                amount=transaction.amount,
                transaction_type=transaction.transaction_type,
                expires_at=timezone.now() + timedelta(minutes=5)
            )
            
            # Send OTP via WhatsApp
            service.send_message(
                request.user.phone_number,
                f"Your EcoCash transfer OTP is: {otp}. Valid for 5 minutes."
            )
            
            # Store transaction ID in session for OTP verification
            request.session['pending_transaction_id'] = transaction.id
            
            messages.success(request, f'OTP sent to your econet number! Transaction ID: {transaction.reference_number}')
            return redirect('econet:verify_otp')
    else:
        form = MoneyTransferForm()
    
    context = {
        'form': form,
        'page_title': 'Send Money',
    }
    return render(request, 'econet/money_transfer.html', context)

def call_ecocash_api(transaction):
    """Call the actual EcoCash API"""
    try:
        # Generate message reference & date
        message_reference = str(uuid.uuid4())
        message_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Include name in message
        if transaction.transaction_type == "Agent":
            message_text = f"Agent:{transaction.ecocash_number}, amount: {transaction.amount}"
        else:
            name = transaction.ecocash_name or ""
            message_text = f"ecocash_number:{transaction.ecocash_number}, amount:{transaction.amount}, name:{name}"
        
        payload = {
            "originator": ECO_ORIGINATOR,
            "destination": ECO_DESTINATION,
            "messageText": message_text,
            "messageReference": message_reference,
            "messageDate": message_date,
            "messageValidity": "",
            "sendDateTime": ""
        }
        
        # Log the API call
        print(f"Calling EcoCash API with payload: {payload}")
        
        # Make API call
        res = requests.post(
            ECO_API_URL,
            json=payload,
            auth=HTTPBasicAuth(ECO_USERNAME, ECO_PASSWORD),
            timeout=30
        )
        
        return {
            'success': res.status_code == 200,
            'status_code': res.status_code,
            'response': res.json() if res.status_code == 200 else {'error': res.text},
            'message_reference': message_reference
        }
        
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f"API request failed: {str(e)}"
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }

@login_required
def verify_otp(request):
    """Verify OTP for transaction"""
    transaction_id = request.session.get('pending_transaction_id')
    
    if not transaction_id:
        messages.error(request, 'No pending transaction found.')
        return redirect('econet:money_transfer')
    
    transaction = get_object_or_404(EcocashTransfers, id=transaction_id, user=request.user)
    
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code')
        
        if not otp_code:
            messages.error(request, 'Please enter the OTP.')
            return render(request, 'econet/verify_otp.html', {'transaction': transaction})
        
        # Find valid OTP
        otp_obj = TransactionOTP.objects.filter(
            user=request.user,
            phone_number=transaction.ecocash_number,
            amount=transaction.amount,
            transaction_type=transaction.transaction_type,
            is_used=False,
            expires_at__gt=timezone.now()
        ).first()
        
        if not otp_obj or otp_obj.otp_code != otp_code:
            messages.error(request, 'Invalid or expired OTP.')
            return render(request, 'econet/verify_otp.html', {'transaction': transaction})
        
        # Mark OTP as used
        otp_obj.is_used = True
        otp_obj.save()
        
        # Process the transaction - CALL ACTUAL ECOCASH API
        try:
            # Call EcoCash API
            api_result = call_ecocash_api(transaction)
            
            if api_result['success']:
                # Update transaction status
                transaction.status = "Successful"
                transaction.processed_at = timezone.now()
                
                # Save API response details
                transaction.description = f"API Response: {json.dumps(api_result['response'])}"
                if 'message_reference' in api_result:
                    transaction.reference_number = api_result['message_reference']
                
                transaction.save()
                
                # Send success notification
                service.send_message(
                    request.user.phone_number,
                    f"EcoCash transfer of ${transaction.amount} to {transaction.ecocash_number} was successful. Ref: {transaction.reference_number}"
                )
                
                # Also notify recipient if not an agent transfer
                if transaction.transaction_type != "Agent":
                    service.send_message(
                        transaction.ecocash_number,
                        f"You have received ${transaction.amount} from {request.user.phone_number}. Ref: {transaction.reference_number}"
                    )
                
                # Clear session
                if 'pending_transaction_id' in request.session:
                    del request.session['pending_transaction_id']
                
                messages.success(request, f'Transaction successful! Reference: {transaction.reference_number}')
                return redirect('econet:transaction_success', reference=transaction.reference_number)
            else:
                # API call failed
                error_msg = api_result.get('error', 'Unknown API error')
                transaction.mark_as_failed(f"API Error: {error_msg}")
                
                # Send failure notification
                service.send_message(
                    request.user.phone_number,
                    f"EcoCash transfer of ${transaction.amount} failed. Error: {error_msg}"
                )
                
                messages.error(request, f'Transaction failed: {error_msg}')
                return redirect('econet:money_transfer')
                
        except Exception as e:
            transaction.mark_as_failed(str(e))
            
            # Send error notification
            service.send_message(
                request.user.phone_number,
                f"EcoCash transfer of ${transaction.amount} encountered an error. Please contact support."
            )
            
            messages.error(request, f'Transaction processing error: {str(e)}')
            return redirect('econet:money_transfer')
    
    context = {
        'transaction': transaction,
        'page_title': 'Verify OTP',
    }
    return render(request, 'econet/verify_otp.html', context)

@login_required
def transaction_success(request, reference):
    """Transaction success page"""
    transaction = get_object_or_404(EcocashTransfers, reference_number=reference, user=request.user)
    
    context = {
        'transaction': transaction,
        'page_title': 'Transaction Successful',
    }
    return render(request, 'econet/transaction_success.html', context)

@login_required
def transaction_history(request):
    """View transaction history"""
    transactions = EcocashTransfers.objects.filter(user=request.user).order_by('-created_at')
    
    # Calculate statistics
    total_transfers = transactions.count()
    successful_transfers = transactions.filter(status="Successful").count()
    pending_transfers = transactions.filter(status="Pending").count()
    failed_transfers = transactions.filter(status="Failed").count()
    total_amount = transactions.filter(status="Successful").aggregate(
        models.Sum('amount')
    )['amount__sum'] or 0
    
    context = {
        'transactions': transactions,
        'total_transfers': total_transfers,
        'successful_transfers': successful_transfers,
        'pending_transfers': pending_transfers,
        'failed_transfers': failed_transfers,
        'total_amount': total_amount,
        'page_title': 'Transaction History',
    }
    return render(request, 'econet/transaction_history.html', context)

@login_required
@csrf_exempt
def resend_otp(request):
    """Resend OTP for pending transaction"""
    if request.method == 'POST':
        transaction_id = request.session.get('pending_transaction_id')
        
        if not transaction_id:
            return JsonResponse({'success': False, 'error': 'No pending transaction'})
        
        transaction = get_object_or_404(EcocashTransfers, id=transaction_id, user=request.user)
        
        # Generate new OTP
        otp = str(random.randint(100000, 999999))
        
        # Save new OTP
        TransactionOTP.objects.create(
            user=request.user,
            otp_code=otp,
            phone_number=transaction.ecocash_number,
            amount=transaction.amount,
            transaction_type=transaction.transaction_type,
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        # Send new OTP via WhatsApp
        service.send_message(
            request.user.phone_number,
            f"Your NEW EcoCash transfer OTP is: {otp}. Valid for 5 minutes."
        )
        
        return JsonResponse({
            'success': True,
            'message': 'OTP resent successfully'
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def cancel_transaction(request):
    """Cancel pending transaction"""
    transaction_id = request.session.get('pending_transaction_id')
    
    if transaction_id:
        transaction = get_object_or_404(EcocashTransfers, id=transaction_id, user=request.user)
        transaction.mark_as_failed("Cancelled by user")
        
        # Send cancellation notification
        service.send_message(
            request.user.phone_number,
            f"EcoCash transfer of ${transaction.amount} to {transaction.ecocash_number} was cancelled."
        )
        
        # Clear session
        if 'pending_transaction_id' in request.session:
            del request.session['pending_transaction_id']
        
        messages.info(request, 'Transaction cancelled.')
    
    return redirect('econet:money_transfer')

# API endpoint for direct transaction (for external systems)
@login_required
@csrf_exempt
def api_create_transaction(request):
    """API endpoint for creating transactions (for WhatsApp bot or other integrations)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tx_type = data.get("type")
            name = data.get("name", "Agent transfer")
            amount = data.get("amount")
            phone = data.get("phone")
            otp = data.get("otp")

            if not tx_type or not amount or not phone or not otp:
                return JsonResponse(
                    {"error": "type, name, amount, phone and otp are required"},
                    status=400
                )

            # Verify OTP
            otp_obj = TransactionOTP.objects.filter(
                user=request.user,
                phone_number=phone,
                amount=amount,
                is_used=False,
                expires_at__gt=timezone.now()
            ).first()
            
            if not otp_obj or otp_obj.otp_code != otp:
                return JsonResponse({"error": "Invalid or expired OTP"}, status=400)

            # Mark OTP as used
            otp_obj.is_used = True
            otp_obj.save()

            # Create transaction record
            transaction = EcocashTransfers.objects.create(
                user=request.user,
                transaction_type=tx_type,
                ecocash_name=name,
                ecocash_number=phone,
                amount=amount,
                status="Pending"
            )

            # Process the transaction
            api_result = call_ecocash_api(transaction)
            
            if api_result['success']:
                transaction.status = "Successful"
                transaction.processed_at = timezone.now()
                if 'message_reference' in api_result:
                    transaction.reference_number = api_result['message_reference']
                transaction.save()
                
                return JsonResponse({
                    "success": True,
                    "message": "Transaction successful",
                    "reference": transaction.reference_number,
                    "api_response": api_result['response']
                })
            else:
                transaction.mark_as_failed(api_result.get('error', 'API error'))
                return JsonResponse({
                    "error": api_result.get('error', 'Transaction failed'),
                    "status_code": api_result.get('status_code', 500)
                }, status=500)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Method not allowed"}, status=405)

# API endpoint to send OTP
@login_required
@csrf_exempt
def api_send_otp(request):
    """API endpoint to send OTP for transaction"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            phone = data.get("phone")
            amount = data.get("amount")
            tx_type = data.get("transaction_type", "User")
            
            if not phone or not amount:
                return JsonResponse({"error": "phone and amount are required"}, status=400)
            
            # Generate OTP
            otp = str(random.randint(100000, 999999))
            
            # Save OTP
            TransactionOTP.objects.create(
                user=request.user,
                otp_code=otp,
                phone_number=phone,
                amount=amount,
                transaction_type=tx_type,
                expires_at=timezone.now() + timedelta(minutes=5)
            )
            
            # Send OTP via WhatsApp
            service.send_message(
                request.user.phone_number,
                f"Your EcoCash transfer OTP is: {otp}. Valid for 5 minutes."
            )
            
            return JsonResponse({
                "message": "OTP sent successfully",
                "otp": otp  # For testing - remove in production
            })
            
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
@csrf_exempt
def api_send_message(request):
    """API endpoint to send a message"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            recipient = data.get('recipient')
            message = data.get('message')
            
            if not recipient or not message:
                return JsonResponse({'success': False, 'error': 'Recipient and message are required'})
            
            # Here you would integrate with actual Econet API
            # For now, we'll simulate sending and log it
            
            # Log as outgoing message
            outgoing = OutgoingMessage.objects.create(
                recipient_id=recipient,
                message_body=message
            )
            
            # You would call your WhatsApp service here
            # service.send_message(recipient, message)
            
            return JsonResponse({
                'success': True,
                'message_id': outgoing.id,
                'message': 'Message sent successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})

@login_required
@csrf_exempt
def api_delete_message(request, message_id):
    """API endpoint to delete a message"""
    if request.method == 'DELETE':
        try:
            message = get_object_or_404(IncomingMessage, id=message_id)
            message.delete()
            
            return JsonResponse({'success': True, 'message': 'Message deleted'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})

@login_required
@csrf_exempt
def api_bulk_action(request):
    """API endpoint for bulk actions"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            message_ids = data.get('message_ids', [])
            
            if not action or not message_ids:
                return JsonResponse({'success': False, 'error': 'Action and message IDs are required'})
            
            messages = IncomingMessage.objects.filter(id__in=message_ids)
            
            if action == 'mark_read':
                messages.update(is_read=True)
                message = f'Marked {len(messages)} messages as read'
            elif action == 'mark_unread':
                messages.update(is_read=False)
                message = f'Marked {len(messages)} messages as unread'
            elif action == 'delete':
                count = messages.count()
                messages.delete()
                message = f'Deleted {count} messages'
            elif action == 'archive':
                # Implement archive logic if you have an archive field
                messages.update(is_archived=True)
                message = f'Archived {len(messages)} messages'
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'})
            
            return JsonResponse({'success': True, 'message': message})
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})

