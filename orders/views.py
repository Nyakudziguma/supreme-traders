from django.shortcuts import render
from django.utils.timezone import now, timedelta
from django.db import transaction as db_transaction
from decimal import Decimal, ROUND_DOWN
from django.core.exceptions import ValidationError
import time
import requests
import asyncio
from deriv.views import process_withdrawal, fetch_payment_agent_transfer_details
import json
from bot.messageFunctions import sendWhatsAppMessage
from bot.utils import Home
from django.urls import reverse
from esolutions.views import (
    purchase_econet_airtime, 
    purchase_econet_bundles, 
    get_merchant_products, 
    process_direct_transfer, 
    resend_transaction_lookup, 
    purchase_netone_airtime, 
    fetch_account_balance
)
import random
from accounts.models import Account
from django.core.mail import EmailMessage
import textwrap
import time
from accounting.models import LedgerAccount, LedgerEntry
from api.models import CashOutTransaction
import requests
import uuid
from datetime import datetime
from django.db import transaction as db_transaction
import re
from bot.models import ClientVerification
from bot.models import Sessions
from difflib import SequenceMatcher 

def phone_number_formatter(phone_number):
    if phone_number[0] == '0':
        phone_number = '263' + phone_number[1:]
    if phone_number[0] == '+':
        phone_number = phone_number[1:]
    if phone_number[0] == '7':
        phone_number = '263' + phone_number
    if phone_number[0] == '2':
        phone_number = phone_number
    return phone_number.replace(" ", "")

def normalize_name(name: str) -> set:
    """
    Normalize a name into a set of lowercase tokens for comparison.
    Removes common prefixes (Mr, Mrs, Ms, Miss, Dr, etc.).
    """
    if not name:
        return set()

    # Remove titles like Mr, Mrs, Dr, etc.
    name = re.sub(r"^(mr|mrs|ms|miss|dr)\.?\s+", "", name, flags=re.IGNORECASE)

    # Split into parts, lowercase, strip punctuation
    tokens = re.split(r"\s+", name.strip())
    return set(token.lower().strip(".") for token in tokens if token)

def names_match(name1: str, name2: str) -> bool:
    """Return True if names are similar enough to allow processing."""
    n1, n2 = normalize_name(name1), normalize_name(name2)
    # Calculate similarity ratio
    ratio = SequenceMatcher(None, n1, n2).ratio()
    return ratio >= 0.75  # Allow minor differences (initials, titles, etc.)

def send_sms(ecocash_number, amount, ecocash_name, destination="263785665537"):
    url = "https://mobile.esolutions.co.zw/bmg/api/single"
    auth = ("CREDSPACEAPI", "wG5PNtxy") 

    # Auto-generate messageReference & messageDate
    message_reference = uuid.uuid4().hex[:12].upper()  
    message_date = datetime.now().strftime("%Y%m%d%H%M%S")

    payload = {
        "originator": "CREDSPACE",
        "destination": destination,
        "messageText": f"ecocash_number:{ecocash_number}, amount:{amount}, name:{ecocash_name}",
        "messageReference": message_reference,
        "messageDate": message_date,
        "messageValidity": "",
        "sendDateTime": ""
    }

    try:
        response = requests.post(url, json=payload, auth=auth)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"SMS sending failed: {str(e)}")
        return None

class OrderProcessor:
    @staticmethod
    def initiate_transaction(trader, order_type, amount, account_number,ecocash_number, ecocash_name):
        print(f'Initiating Transaction .......... {amount}')
        recent_transaction = trader.orders.filter(created_at__gte=now() - timedelta(minutes=1),).exists()
        print(f'Recent Transaction: {recent_transaction}')
        if recent_transaction:
            message = "You must wait for 3 minute before initiating another transaction."
            Home(trader.phone_number, message)
            raise ValidationError("You must wait 3 minutes before initiating another transaction to avoid duplicates.")
        
        limit = Limit.objects.get(transaction_type=order_type)
        
        if amount <limit.minimum:
            message = f"Amount should be great than ${limit.minimum}"
            Home(trader.phone_number, message)
            raise ValidationError(f"Amount should be great than ${limit.minimum}")

        balance = Balance.objects.filter(name='main').first()
        if not balance or balance.balance < amount and order_type=='Buy':
            message = "An error occured while processing your transaction. Please get in touch with our support team."
            Home(trader.phone_number, message)
            raise ValidationError("Insufficient balance to perform this transaction.")

        total_deduction = amount 
        if balance.balance < total_deduction and order_type=='Buy':
            message = "An error occured while processing your transaction. Please get in touch with our support team."
            Home(trader.phone_number, message)
            raise ValidationError("Insufficient balance to cover the amount")

        with db_transaction.atomic():
            charge = 0
            fee= Fee.objects.get(transaction_type=order_type)
            if order_type =='Buy':
                if amount <= 5:
                    charge = fee.below_5_charge
                elif amount <= 10:
                    charge = fee.below_10_charge
                else:
                    fee_percentage = Decimal(fee.percentage) / Decimal(100)
                    net_amount = (amount / (1 + fee_percentage)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                    charge = (amount - net_amount).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

            else:
                charge=0
            try:
                order = Order.objects.create(
                trader=trader,
                order_type=order_type,
                amount=amount,
                account_number=account_number,
                ecocash_number=ecocash_number,
                ecocash_name = ecocash_name,
                charge=charge,
                status='Pending'
                )
            except Exception as e:
                print(e)

            AuditLog.objects.create(
                trader=trader,
                action=f"Initiated {order_type} order for {amount} with charge {charge}."
            )
            print(order)
            return order

        
    @staticmethod
    def process_order(order_id, status):

        with db_transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            if order.status != 'Pending':
                raise ValidationError("This order has already been processed.")

            order.status = status
            order.processed_at = now()
            order.save()

            AuditLog.objects.create(
                trader=order.trader,
                action=f"Order {order.id} marked as {status}."
            )

            if status == 'Failed':
                trader_balance = Balance.objects.filter(name=order.trader.username).first()
                if trader_balance:
                    trader_balance.balance += order.amount + order.charge
                    trader_balance.save()

            return order
    
    @staticmethod
    def create_notification(recipient, message, transaction):
        with db_transaction.atomic():
            notification = Notification.objects.create(
                recipient=recipient,
                message=message,
                transaction=transaction
            )
            Home(recipient.phone_number, message)

            try:
                mail_subject = 'FINPAL NOTIFICATION'

                message = textwrap.dedent(f"""
                    <html>
                        <body>
                            <p><strong>Hello {recipient.first_name} </strong></p>
                            <p>{message}</p>
                            <p>Please click <a href="https://finance.zimbofx.co.zw"> <strong> Here </strong> login to the system</a></p>
                        </body>
                    </html>
                """)

                send_email = EmailMessage(mail_subject, message, to=[recipient.email])
                send_email.content_subtype = 'html'  
                send_email.send()
            except Exception as e:
                pass
            
            return notification


def handle_order(trader, order_type, amount, account_number, email,ecocash_number='', txn_id='', ecocash_name='',code='', token='', Merchant='', RechargeAccount='',productCode=''):
    print(f'Handling Order .......... {amount} {order_type} {account_number}')

    # Force CR prefix
    if not account_number.upper().startswith('CR'):
        account_number = 'CR' + account_number.lstrip('crCR')

    # === INITIATE TRANSACTION ===
    order = OrderProcessor.initiate_transaction(
        trader, order_type, amount,
        account_number, ecocash_number, ecocash_name
    )

    if isinstance(order, str):
        print(f"Transaction initiation failed: {order}")
        return

    # =====================================================================
    #                      SELL ORDER PROCESSING ONLY
    # =====================================================================
    if order_type == 'Sell':

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Fetch Deriv name
        details_result = loop.run_until_complete(
            fetch_payment_agent_transfer_details(amount, account_number)
        )

        if not (isinstance(details_result, dict) and 'client_to_full_name' in details_result):
            Home(trader.phone_number, "⚠️ Could not fetch Deriv account details.")
            OrderProcessor.process_order(order.id, 'Failed')
            return

        deriv_name = details_result['client_to_full_name']

        # Normalize names
        deriv_tokens = normalize_name(deriv_name)
        local_tokens = normalize_name(ecocash_name)

        # Must match at least 1 token
        if not (deriv_tokens & local_tokens):
            msg = (
                "⚠️ Name Validation Failed\n\n"
                f"Deriv Name: {deriv_name}\n"
                f"Ecocash Name: {ecocash_name}\n\n"
                "Names must match to proceed with the SELL transaction."
            )
            Home(trader.phone_number, msg)
            OrderProcessor.process_order(order.id, 'Failed')
            return

        # =====================================================================
        #                    PROCESS DERIV WITHDRAWAL
        # =====================================================================
        withdrawal_response = asyncio.run(
            process_withdrawal(amount, account_number, code, token)
        )
        print("withdrawal_response:", withdrawal_response)

        paymentagent_transfer = withdrawal_response.get('paymentagent_withdraw') if withdrawal_response else None

        with db_transaction.atomic():

            # SUCCESS
            if paymentagent_transfer == 1:

                OrderProcessor.process_order(order.id, 'Completed')

                # Create Transaction record
                Transaction.objects.create(
                    order=order,
                    trader=trader,
                    transaction_type=order_type,
                    amount=order.amount,
                    charge=0,
                    status='Successful',
                    deriv_cr=account_number,
                    ecocash_phone=ecocash_number,
                    ecocash_txn_id=txn_id,
                    extras=str(withdrawal_response)
                )

                # Clean phone number
                clean_number = re.sub(r"\s+", "", ecocash_number)

                # Send SMS to Admin
                send_sms(clean_number, amount, deriv_name)

                # WhatsApp confirmation
                msg = (
                    "Withdrawal Successful! ✅\n\n"
                    f"Amount: ${amount}\n"
                    f"Deriv Account: {account_number}\n"
                    f"Ecocash Number: {clean_number}\n\n"
                    "Your funds will reflect shortly."
                )
                Home(trader.phone_number, msg)

                return

            # FAILURE
            else:
                OrderProcessor.process_order(order.id, 'Failed')

                Transaction.objects.create(
                    order=order,
                    trader=trader,
                    transaction_type=order_type,
                    amount=order.amount,
                    charge=0,
                    status='Failed',
                    deriv_cr=account_number,
                    ecocash_phone=ecocash_number,
                    ecocash_txn_id=txn_id,
                    extras=str(withdrawal_response)
                )

                Home(trader.phone_number, "❌ Withdrawal Failed. Please try again or contact support.")
                return

