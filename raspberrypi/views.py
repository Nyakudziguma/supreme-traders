from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import IncomingMessage, IncomingCall, OutgoingMessage
from .serializers import (
    IncomingMessageSerializer,
    IncomingCallSerializer,
    OutgoingMessageSerializer
)
import re
from decimal import Decimal
from ecocash.models import CashOutTransaction, CashInTransaction
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import IncomingMessage
from orders.models import Balance
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator


def normalize_phone(number):
    """
    Normalize Ecocash numbers to format: 786xxxxxxx
    Supports: +263786..., 263786..., 0786...
    """
    if not number:
        return None
    number = number.strip()
    if number.startswith("+"):
        number = number[1:]
    if number.startswith("263"):
        number = number[3:]
    if number.startswith("0"):
        number = number[1:]
    return number


@api_view(['POST'])
@authentication_classes([BasicAuthentication])
@permission_classes([IsAuthenticated])
def receive_message(request):
    sender = request.data.get("sender")
    message = request.data.get("message")
    
    # Add logging for debugging
    print(f"Received message from {sender}: {message}")

    try:
        # Always save raw message first
        msg_data = {
            "sender_id": sender,
            "message_body": message,
        }
        serializer = IncomingMessageSerializer(data=msg_data)
        if serializer.is_valid():
            serializer.save()

        # Only handle Ecocash messages
        if sender == "#2236333136343553544":
            # Handle CashOut confirmation
            if "Ecocash: CashOut Confirmation" in message:
                # Try to match the complete pattern first
                full_pattern = r"USD\s+([\d\.]+)\s+transfered\s+from\s+(.+?),(\d+).*?Txn ID\s*:(\S+).*?New Wallet balance:\s*USD\s*([\d\.]+)"
                match = re.search(full_pattern, message, re.IGNORECASE)

                if match:
                    print("Matched complete CashOut message with balance")
                    # Complete message with balance
                    amount = Decimal(match.group(1).strip().rstrip("."))
                    name = match.group(2).strip()
                    phone_raw = match.group(3).strip()
                    phone = normalize_phone(phone_raw)
                    txn_id = match.group(4).strip().rstrip(".")
                    new_bal = Decimal(match.group(5).strip().rstrip("."))
                    
                    # Get previous balance (from non-flagged transactions)
                    last_txn = CashOutTransaction.objects.filter(flagged=False).order_by("-timestamp").first()
                    prev_bal = last_txn.new_bal if last_txn else Decimal("0.00")
                    
                    # Business rules
                    low_limit = amount < Decimal("1.5")
                    flagged = False
                    flag_reason = None
                    flagged_by = None
                    
                    if abs((new_bal - amount) - prev_bal) > Decimal("0.01"):
                        flagged = True
                        flag_reason = "Suspicious transaction"
                        flagged_by = "System"
                    
                    # Save transaction
                    txn = CashOutTransaction.objects.create(
                        amount=str(amount),
                        name=name,
                        phone=phone,
                        txn_id=txn_id,
                        body=message,
                        prev_bal=prev_bal,
                        new_bal=new_bal,
                        low_limit=low_limit,
                        flagged=flagged,
                        flag_reason=flag_reason,
                        flagged_by=flagged_by,
                    )
                    
                    # Update Agent balance for CashOut (add amount)
                    if not flagged:
                        try:
                            agent_balance = Balance.objects.get(name="Agent")
                            agent_balance.balance = agent_balance.balance + amount
                            agent_balance.save()
                        except Balance.DoesNotExist:
                            Balance.objects.create(name="Agent", balance=amount)
                    
                    return Response(
                        {"message": "CashOut transaction saved", "txn_id": txn.txn_id},
                        status=status.HTTP_201_CREATED,
                    )
                else:
                    # Incomplete message - try to extract as much information as possible
                    # Pattern for amount, name, and phone
                    basic_pattern = r"USD\s+([\d\.]+)\s+transfered\s+from\s+(.+?),(\d+)"
                    basic_match = re.search(basic_pattern, message, re.IGNORECASE)
                    
                    if basic_match:
                        amount = Decimal(basic_match.group(1).strip().rstrip("."))
                        name = basic_match.group(2).strip()
                        phone_raw = basic_match.group(3).strip()
                        phone = normalize_phone(phone_raw)
                        
                        # Try to extract transaction ID if present
                        txn_id_pattern = r"Txn ID\s*:(\S+)"
                        txn_id_match = re.search(txn_id_pattern, message, re.IGNORECASE)
                        txn_id = txn_id_match.group(1).strip().rstrip(".") if txn_id_match else "PENDING"
                        
                        # Try to extract balance if present
                        balance_pattern = r"New Wallet balance:\s*USD\s*([\d\.]+)"
                        balance_match = re.search(balance_pattern, message, re.IGNORECASE)
                        
                        # Check for various partial balance patterns
                        partial_patterns = [
                            r"New Wallet balance:\s*USD\s*$",  # Ends with "New Wallet balance: USD"
                            r"New Wallet balance:\s*$",        # Ends with "New Wallet balance:"
                            r"New Wallet\s*$",                # Ends with "New Wallet"
                            r"New\s*$"                        # Ends with "New"
                        ]
                        
                        partial_balance_match = False
                        for pattern in partial_patterns:
                            if re.search(pattern, message, re.IGNORECASE):
                                partial_balance_match = True
                                print(f"Detected partial balance pattern: {pattern}")
                                break
                        
                        print(f"Basic match: Amount={amount}, Name={name}, Phone={phone}, TxnID={txn_id}")
                        
                        # Get previous balance (from non-flagged transactions)
                        last_txn = CashOutTransaction.objects.filter(flagged=False).order_by("-timestamp").first()
                        prev_bal = last_txn.new_bal if last_txn else Decimal("0.00")
                        
                        # Check for existing incomplete transaction with same details
                        existing_txn = None
                        recent_incomplete_txns = CashOutTransaction.objects.filter(
                            flagged=True,
                            flag_reason__contains="Incomplete",
                            timestamp__gte=timezone.now() - timedelta(seconds=60)
                        ).order_by("-timestamp")
                        
                        for txn in recent_incomplete_txns:
                            # Compare basic details to find a match
                            if (str(amount) in txn.amount and 
                                name in txn.name and 
                                phone in txn.phone):
                                existing_txn = txn
                                print(f"Found existing incomplete transaction: {txn.txn_id}")
                                break
                        
                        if balance_match:
                            # We have a balance in this message
                            new_bal = Decimal(balance_match.group(1).strip().rstrip("."))
                            
                            if existing_txn:
                                # Update existing transaction
                                existing_txn.txn_id = txn_id if txn_id != "PENDING" else existing_txn.txn_id
                                existing_txn.new_bal = new_bal
                                
                                # Apply business rules
                                flagged = False
                                flag_reason = None
                                
                                if abs((new_bal - amount) - prev_bal) > Decimal("0.01"):
                                    flagged = True
                                    flag_reason = "Suspicious transaction"
                                    flagged_by = "System"
                                
                                existing_txn.flagged = flagged
                                existing_txn.flag_reason = flag_reason
                                existing_txn.flagged_by = flagged_by if flagged else None
                                existing_txn.save()
                                
                                # Update Agent balance if transaction is now valid
                                if not flagged:
                                    try:
                                        agent_balance = Balance.objects.get(name="Agent")
                                        agent_balance.balance = agent_balance.balance + amount
                                        agent_balance.save()
                                    except Balance.DoesNotExist:
                                        Balance.objects.create(name="Agent", balance=amount)
                                
                                return Response(
                                    {"message": "Updated incomplete CashOut transaction", "txn_id": existing_txn.txn_id},
                                    status=status.HTTP_200_OK,
                                )
                            else:
                                # Create new complete transaction
                                flagged = False
                                flag_reason = None
                                flagged_by = None
                                
                                if abs((new_bal - amount) - prev_bal) > Decimal("0.01"):
                                    flagged = False
                                    flag_reason = "Suspicious transaction"
                                    flagged_by = "System"
                                
                                txn = CashOutTransaction.objects.create(
                                    amount=str(amount),
                                    name=name,
                                    phone=phone,
                                    txn_id=txn_id,
                                    body=message,
                                    prev_bal=prev_bal,
                                    new_bal=new_bal,
                                    low_limit=amount < Decimal("1.5"),
                                    flagged=flagged,
                                    flag_reason=flag_reason,
                                    flagged_by=flagged_by,
                                )
                                
                                # Update Agent balance for CashOut (add amount)
                                if not flagged:
                                    try:
                                        agent_balance = Balance.objects.get(name="Agent")
                                        agent_balance.balance = agent_balance.balance + amount
                                        agent_balance.save()
                                    except Balance.DoesNotExist:
                                        Balance.objects.create(name="Agent", balance=amount)
                                
                                return Response(
                                    {"message": "CashOut transaction saved", "txn_id": txn.txn_id},
                                    status=status.HTTP_201_CREATED,
                                )
                        elif partial_balance_match:
                            # We have a partial "New Wallet balance" string but no actual balance
                            # Save as incomplete and wait for the balance
                            print("Detected partial balance message")
                            
                            if existing_txn:
                                # Update existing transaction with any new info
                                if txn_id != "PENDING":
                                    existing_txn.txn_id = txn_id
                                    existing_txn.save()
                                return Response(
                                    {"message": "Partial update to incomplete CashOut transaction", "txn_id": existing_txn.txn_id},
                                    status=status.HTTP_200_OK,
                                )
                            else:
                                # Create new incomplete transaction
                                txn = CashOutTransaction.objects.create(
                                    amount=str(amount),
                                    name=name,
                                    phone=phone,
                                    txn_id=txn_id,
                                    body=message,
                                    prev_bal=prev_bal,
                                    new_bal=prev_bal,  # Use previous balance as placeholder
                                    low_limit=amount < Decimal("1.5"),
                                    flagged=True,
                                    flag_reason="Incomplete and suspicious Transaction",
                                    flagged_by="System",
                                )
                                
                                print(f"Created incomplete transaction with ID: {txn.txn_id}")
                                
                                return Response(
                                    {"message": "Incomplete CashOut transaction saved", "txn_id": txn.txn_id},
                                    status=status.HTTP_201_CREATED,
                                )
                        else:
                            # Create or update incomplete transaction
                            if existing_txn:
                                # Update existing transaction with any new info
                                if txn_id != "PENDING" and existing_txn.txn_id == "PENDING":
                                    existing_txn.txn_id = txn_id
                                    existing_txn.save()
                                    
                                return Response(
                                    {"message": "Updated incomplete CashOut transaction", "txn_id": existing_txn.txn_id},
                                    status=status.HTTP_200_OK,
                                )
                            else:
                                # Create new incomplete transaction
                                txn = CashOutTransaction.objects.create(
                                    amount=str(amount),
                                    name=name,
                                    phone=phone,
                                    txn_id=txn_id,
                                    body=message,
                                    prev_bal=prev_bal,
                                    new_bal=prev_bal,  # Use previous balance as placeholder
                                    low_limit=amount < Decimal("1.5"),
                                    flagged=True,
                                    flag_reason="Incomplete and suspicious Transaction",
                                    flagged_by="System",
                                )
                                
                                print(f"Created incomplete transaction with ID: {txn.txn_id}")
                                
                                return Response(
                                    {"message": "Incomplete CashOut transaction saved", "txn_id": txn.txn_id},
                                    status=status.HTTP_201_CREATED,
                                )
            
            # Check if this is a balance-only or transaction ID fragment
            # This could be a continuation of a previous message
            else:
                # Enhanced patterns to handle various balance message formats
                balance_patterns = [
                    r"^(?:New Wallet balance:\s*USD\s*)?([\d\.]+)\s*\.$",  # Full or just number: "New Wallet balance: USD 212.44." or "212.44."
                    r"^(?:balance:\s*USD\s*)([\d\.]+)\s*\.$",              # Partial "balance: USD 212.44."
                    r"^(?:USD\s*)([\d\.]+)\s*\.$"                          # Just "USD 212.44."
                ]
                
                balance_match = None
                balance_value = None
                
                # Try each pattern
                for pattern in balance_patterns:
                    match = re.search(pattern, message, re.IGNORECASE)
                    if match:
                        balance_value = Decimal(match.group(1).strip())
                        balance_match = match
                        print(f"Matched balance pattern: {pattern} with value: {balance_value}")
                        break
                
                # Look for transaction ID fragment
                txn_id_fragment_pattern = r"^([A-Za-z0-9\.]+)\s*\.\s*New Wallet balance:\s*USD\s*([\d\.]+)\s*\.$"
                txn_id_fragment_match = re.search(txn_id_fragment_pattern, message)
                
                if balance_match:
                    # This is a balance value (in various formats)
                    new_bal = balance_value
                    print(f"Detected balance message with value: {new_bal}")
                    
                    # Look for recent incomplete transactions
                    incomplete_txns = CashOutTransaction.objects.filter(
                        flagged=True, 
                        flag_reason__contains="Incomplete",
                        timestamp__gte=timezone.now() - timedelta(seconds=60)
                    ).order_by("-timestamp")
                    
                    print(f"Found {incomplete_txns.count()} potential incomplete transactions")
                    
                    if incomplete_txns.exists():
                        # Get the most recent incomplete transaction
                        incomplete_txn = incomplete_txns.first()
                        print(f"Selected incomplete transaction: {incomplete_txn.txn_id} from {incomplete_txn.timestamp}")
                        
                        # Update the transaction with the balance
                        amount = Decimal(incomplete_txn.amount)
                        
                        # Get previous balance from non-flagged transactions
                        last_txn = CashOutTransaction.objects.filter(
                            flagged=False, 
                            timestamp__lt=incomplete_txn.timestamp
                        ).order_by("-timestamp").first()
                        prev_bal = last_txn.new_bal if last_txn else Decimal("0.00")
                        
                        # Apply business rules
                        flagged = False
                        flag_reason = None
                        flagged_by = None
                        
                        if abs((new_bal - amount) - prev_bal) > Decimal("0.01"):
                            flagged = False
                            flag_reason = "Suspicious transaction"
                            flagged_by = "System"
                        
                        # Update the transaction
                        incomplete_txn.new_bal = new_bal
                        incomplete_txn.prev_bal = prev_bal
                        incomplete_txn.flagged = flagged
                        incomplete_txn.flag_reason = flag_reason
                        incomplete_txn.flagged_by = flagged_by
                        incomplete_txn.save()
                        
                        # Update Agent balance for CashOut (add amount) if not flagged
                        if not flagged:
                            try:
                                agent_balance = Balance.objects.get(name="Agent")
                                agent_balance.balance = agent_balance.balance + amount
                                agent_balance.save()
                            except Balance.DoesNotExist:
                                Balance.objects.create(name="Agent", balance=amount)
                        
                        return Response(
                            {"message": "Incomplete CashOut transaction updated with balance", "txn_id": incomplete_txn.txn_id},
                            status=status.HTTP_200_OK,
                        )
                    
                    # No incomplete transaction found
                    return Response({"status": "received", "note": "balance message received but no pending transaction"}, 
                                  status=status.HTTP_200_OK)
                
                elif txn_id_fragment_match:
                    # This is a transaction ID fragment with balance
                    txn_id_suffix = txn_id_fragment_match.group(1).strip()
                    new_bal = Decimal(txn_id_fragment_match.group(2).strip())
                    
                    print(f"Detected txn_id fragment with balance: txn_id suffix={txn_id_suffix}, balance={new_bal}")
                    
                    # Look for recent incomplete transactions that might match this txn_id fragment
                    incomplete_txns = CashOutTransaction.objects.filter(
                        flagged=True, 
                        flag_reason__contains="Incomplete",
                        timestamp__gte=timezone.now() - timedelta(seconds=60)
                    ).order_by("-timestamp")
                    
                    for txn in incomplete_txns:
                        # Check if this transaction needs a txn_id update
                        if txn.txn_id == "PENDING" or txn_id_suffix not in txn.txn_id:
                            # Update the transaction ID and balance
                            amount = Decimal(txn.amount)
                            
                            # Get previous balance
                            last_txn = CashOutTransaction.objects.filter(
                                flagged=False, 
                                timestamp__lt=txn.timestamp
                            ).order_by("-timestamp").first()
                            prev_bal = last_txn.new_bal if last_txn else Decimal("0.00")
                            
                            # Apply business rules
                            flagged = False
                            flag_reason = None
                            flagged_by = None
                            
                            if abs((new_bal - amount) - prev_bal) > Decimal("0.01"):
                                flagged = True
                                flag_reason = "Suspicious transaction"
                                flagged_by = "System"
                            
                            # Update the transaction
                            if txn.txn_id == "PENDING":
                                txn.txn_id = txn_id_suffix
                            else:
                                # This might be a continuation of the txn_id
                                # Try to reconstruct the full txn_id
                                txn.txn_id = txn.txn_id + txn_id_suffix
                                
                            txn.new_bal = new_bal
                            txn.prev_bal = prev_bal
                            txn.flagged = flagged
                            txn.flag_reason = flag_reason
                            txn.flagged_by = flagged_by
                            txn.save()
                            
                            # Update Agent balance for CashOut (add amount) if not flagged
                            if not flagged:
                                try:
                                    agent_balance = Balance.objects.get(name="Agent")
                                    agent_balance.balance = agent_balance.balance + amount
                                    agent_balance.save()
                                except Balance.DoesNotExist:
                                    Balance.objects.create(name="Agent", balance=amount)
                            
                            return Response(
                                {"message": "Incomplete CashOut transaction updated", "txn_id": txn.txn_id},
                                status=status.HTTP_200_OK,
                            )
                    
                    # No matching incomplete transaction
                    return Response({"status": "received", "note": "fragment received but no matching transaction found"}, 
                                   status=status.HTTP_200_OK)

            # Handle CashIn transaction
            if "Cash-In sent to" in message:
                pattern = r"USD([\d\.]+)\s+Cash-In\s+sent\s+to\s+(.+?).\s+COMM:\s+[\d\.]+.\s+TXN ID:(\S+).\s+New balance:\s*USD\s*([\d\.]+)"
                match = re.search(pattern, message, re.IGNORECASE)

                if match:
                    amount = Decimal(match.group(1).strip().rstrip("."))
                    name = match.group(2).strip()
                    txn_id = match.group(3).strip().rstrip(".")
                    new_bal = Decimal(match.group(4).strip().rstrip("."))

                    # Save CashIn transaction
                    txn = CashInTransaction.objects.create(
                        amount=amount,
                        name=name,
                        txn_id=txn_id,
                        body=message,
                        new_bal=new_bal,
                    )

                    # Update Agent balance for CashIn (subtract amount)
                    try:
                        agent_balance = Balance.objects.get(name="Agent")
                        agent_balance.balance = agent_balance.balance - amount
                        agent_balance.save()
                    except Balance.DoesNotExist:
                        Balance.objects.create(name="Agent", balance=-amount)

                    return Response(
                        {"message": "CashIn transaction saved", "txn_id": txn.txn_id},
                        status=status.HTTP_201_CREATED,
                    )

        # Default response (non-Ecocash or unparsed message)
        return Response({"status": "received"}, status=status.HTTP_200_OK)

    except Exception as e:
        # Log the exception for debugging
        print(f"Exception in receive_message: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Catch unexpected errors but still ACK to stop retries
        return Response(
            {"status": "received", "note": f"error logged: {str(e)}"},
            status=status.HTTP_200_OK,
        )
        
# def process_cashout_transaction(amount, name, phone, txn_id, message, new_bal):
#     """Helper function to process complete CashOut transactions"""
#     # Get previous balance (default 0 if no transactions yet)
#     last_txn = CashOutTransaction.objects.filter(flagged=False).order_by("-timestamp").first()
#     prev_bal = last_txn.new_bal if last_txn else Decimal("0.00")

#     # Business rules
#     low_limit = amount < Decimal("1.5")
#     flagged = False
#     flag_reason = None
#     flagged_by = None

#     if abs((new_bal - amount) - prev_bal) > Decimal("0.01"):
#         flagged = True
#         flag_reason = "Suspicious transaction"
#         flagged_by = "System"

#     # Save transaction
#     txn = CashOutTransaction.objects.create(
#         amount=str(amount),
#         name=name,
#         phone=phone,
#         txn_id=txn_id,
#         body=message,
#         prev_bal=prev_bal,
#         new_bal=new_bal,
#         low_limit=low_limit,
#         flagged=flagged,
#         flag_reason=flag_reason,
#         flagged_by=flagged_by,
#     )

#     # Update Agent balance for CashOut (add amount)
#     try:
#         agent_balance = Balance.objects.get(name="Agent")
#         agent_balance.balance = agent_balance.balance + amount
#         agent_balance.save()
#     except Balance.DoesNotExist:
#         Balance.objects.create(name="Agent", balance=amount)

#     return Response(
#         {"message": "CashOut transaction saved", "txn_id": txn.txn_id},
#         status=status.HTTP_201_CREATED,
#     )
    
# def receive_message(request):
#     sender = request.data.get("sender")
#     message = request.data.get("message")

#     # Only handle Ecocash messages
#     if sender == "#2236333136343553544" and "Ecocash: CashOut Confirmation" in message:
#         try:
#             # Regex to extract details
#             pattern = r"USD\s+([\d\.]+)\s+transfered\s+from\s+(.+?),(\d+).*?Txn ID\s*:(\S+).*?New Wallet balance:\s*USD\s*([\d\.]+)"
#             match = re.search(pattern, message, re.IGNORECASE)

#             if not match:
#                 return Response({"error": "Message format not recognized"}, status=status.HTTP_400_BAD_REQUEST)

#             # Clean & parse fields
#             amount = Decimal(match.group(1).strip().rstrip("."))
#             name = match.group(2).strip()
#             phone_raw = match.group(3).strip()
#             phone = normalize_phone(phone_raw)
#             txn_id = match.group(4).strip().rstrip(".")
#             new_bal = Decimal(match.group(5).strip().rstrip("."))

#             # Get previous balance (default 0 if no transactions yet)
#             last_txn = CashOutTransaction.objects.order_by("-timestamp").first()
#             prev_bal = last_txn.new_bal if last_txn else Decimal("0.00")

#             # Business rules
#             low_limit = amount < Decimal("1.5")
#             flagged = True
#             flag_reason = None
#             flagged_by = None

#             if abs((new_bal-amount) - prev_bal) > Decimal("0.01"):
#                 flagged = True
#                 flag_reason = "Suspicious transaction"
#                 flagged_by = "System"

#             # Save transaction
#             txn = CashOutTransaction.objects.create(
#                 amount=str(amount),
#                 name=name,
#                 phone=phone,
#                 txn_id=txn_id,
#                 body=message,
#                 prev_bal=prev_bal,
#                 new_bal=new_bal,
#                 low_limit=low_limit,
#                 flagged=flagged,
#                 flag_reason=flag_reason,
#                 flagged_by=flagged_by,
#             )

#             # ALSO save raw message in IncomingMessage
#             msg_data = {
#                 "sender_id": sender,
#                 "message_body": message,
#             }
#             serializer = IncomingMessageSerializer(data=msg_data)
#             if serializer.is_valid():
#                 serializer.save()

#             return Response(
#                 {"message": "CashOut transaction saved", "txn_id": txn.txn_id},
#                 status=status.HTTP_201_CREATED,
#             )

#         except Exception as e:
#             return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

#     else:
#         # Save raw SMS
#         data = {
#             "sender_id": sender,
#             "message_body": message,
#         }
#         serializer = IncomingMessageSerializer(data=data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         else:
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
@authentication_classes([BasicAuthentication])
@permission_classes([IsAuthenticated])
def receive_incoming_call(request):
    serializer = IncomingCallSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "Incoming call logged successfully"}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([BasicAuthentication])
@permission_classes([IsAuthenticated])
def log_outgoing_message(request):
    serializer = OutgoingMessageSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "Outgoing message saved successfully"}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET'])
def get_messages(request):
    # Get all messages ordered by most recent
    messages = IncomingMessage.objects.all().order_by('-received_at')
    
    # Initialize paginator
    paginator = Paginator(messages, 20)  # Show 20 messages per page
    page_number = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.get_page(page_number)
    except:
        page_obj = paginator.get_page(1)
    
    # Prepare data
    data = [
        {
            "id": msg.id,
            "sender": msg.sender_id,
            "content": msg.message_body,
            "time": msg.received_at.strftime("%I:%M %p"),
            "date": msg.received_at.strftime("%b %d, %Y"),
            "unread": True  # you can later track this properly
        }
        for msg in page_obj
    ]
    
    # Return data with pagination info
    return Response({
        "messages": data,
        "page": {
            "current": page_obj.number,
            "total": paginator.num_pages,
            "count": paginator.count,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
            "previous_page_number": page_obj.previous_page_number() if page_obj.has_previous() else None,
        }
    })

