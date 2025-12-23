# whatsapp/services.py (updated)
from difflib import SequenceMatcher
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from accounts.models import User
from finance.models import EcoCashTransaction, TransactionReceipt, TransactionCharge
from .models import WhatsAppSession, WhatsAppMessage
from .ocr_service import EcoCashOCRService
from decimal import Decimal, InvalidOperation
import base64
import io
from .models import InitiateOrders, EcocashPop, ClientVerification
from ecocash.models import CashOutTransaction
import re
import uuid
from datetime import datetime
import asyncio
from datetime import timedelta

class WhatsAppService:
    def __init__(self):
        self.api_url = settings.WHATSAPP_URL
        self.api_token = settings.WHATSAPP_TOKEN
        self.ocr_service = EcoCashOCRService()
        self.sms_url = settings.SMS_API_URL
        self.sms_auth = (settings.SMS_API_USER, settings.SMS_API_PASSWORD)
        self.deriv_app_id = settings.DERIV_APP_ID
    
    def send_message(self, phone_number, message):
        headers = {"Authorization": self.api_token}
        payload = {"messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone_number,
                "type": "text",
                "text": {"body": message}
                }
        response = requests.post(self.api_url, headers=headers, json=payload)
        ans = response.json()
        self.log_message(phone_number, message, 'outgoing')
        print("Response: ", ans)
        return True
    
    def send_menu_message(self, phone_number):
        headers = {"Authorization": self.api_token}
        payload = {"messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone_number,
                "type": "interactive",
                    "interactive": {
                    "type": "list",
                    "header": {
                        "type": "text",
                        "text": ''
                    },
                    "body": {
                        "text": "👋 Welcome to Supreme Traders I’m Supreme AI, your virtual assistant 🤖. \n\nTap The Supreme Menu button below to explore your options."
                    },
                    "action":
                        {
                            "button": "🏠 Supreme Menu",
                            "sections": [
                                {
                                    "title": "Options",
                                    "rows": [
                                        {
                                            "id": "deriv_deposit",
                                            "title": "💸 Deriv Deposits",
                                        },
                                        {
                                            "id": "withdraw",
                                            "title": "🏧 Deriv Withdrawals",
                                        },
                                        {
                                            "id": "trading_signals",
                                            "title": "📈 Trading Signals",
                                        },
                                        {
                                            "id": "forex_training",
                                            "title": "📖 Forex Training",
                                            
                                        },
                                        {
                                            "id": "books",
                                            "title": "📚 Books",
                                            
                                        },
                                        {
                                            "id": "contact_support",
                                            "title": "📞 Contact Support",
                                            
                                        },

                                        
                                    ]

                                }
                            ]
                        }
                }
            
                }
        response = requests.post(self.api_url, headers=headers, json=payload)
        ans = response.json()
        print(ans)
        return True
    
    def deriv_authentication(self, phone_number, message):
        headers = {"Authorization": self.api_token}
        payload = {"messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone_number,
                "type": "interactive",
                "interactive": {
                        "type": "cta_url",
                        "body": {
                        "text": message
                        },
                        "action": {
                        "name": "cta_url",
                        "parameters": {
                            "display_text": "Login",
                            "url": f"https://oauth.deriv.com/oauth2/authorize?app_id=115043&affiliate_token={phone_number}"
                        }
                        }
                    }
                    }
                            
                
        response = requests.post(settings.WHATSAPP_URL, headers=headers, json=payload)
        ans = response.json()
        return

    def send_signals_message(self, phone_number):
        from subscriptions.models import SubscriptionPlans
        headers = {"Authorization": self.api_token}
        plans = SubscriptionPlans.objects.all()
        rows = [
            {
            "id": plan.id,
            "title": f"📈 {plan.plan_name} ${plan.price}",
            }
            for plan in plans
        ]
        
        payload = {"messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "interactive",
                "interactive": {
                "type": "list",
                "header": {
                "type": "text",
                "text": '📊 Trading Signals'
                },
                "body": {
                "text": "Our premium trading signals service provides accurate market insights. \n\nChoose your subscription plan by clicking on the view plans button below."
                },
                "footer": {
                "text": "Terms and Conditions apply."
                },
                "action":
                {
                    "button": "View Plans",
                    "sections": [
                    {
                        "title": "Options",
                        "rows": rows
                    }
                    ]
                }
            }
            
            }
        response = requests.post(self.api_url, headers=headers, json=payload)
        ans = response.json()
        print(ans)

    def send_books_message(self, phone_number):
        from books.models import Book
        headers = {"Authorization": self.api_token}
        books = Book.objects.all()
        rows = [
            {
            "id": book.id,
            "title": f"📈 {book.title}",
            }
            for book in books
        ]
        
        payload = {"messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "interactive",
                "interactive": {
                "type": "list",
                "header": {
                "type": "text",
                "text": 'Trading Books'
                },
                "body": {
                "text": "I see you're interested in our trading books collection! We have both free and premium options available. \n\nChoose your book by clicking on the view books button below."
                },
                "footer": {
                "text": "Terms and Conditions apply."
                },
                "action":
                {
                    "button": "View Books",
                    "sections": [
                    {
                        "title": "Options",
                        "rows": rows
                    }
                    ]
                }
            }
            
            }
        response = requests.post(self.api_url, headers=headers, json=payload)
        ans = response.json()
        print(ans)

    def send_documents(self, phone_number, document_file, caption, title):
        headers = {"Authorization": self.api_token }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "document",
            "document": {
                "link": f"https://supreme.finpal.co.zw{document_file}",
                "filename": title,
                "caption":caption
            }
        }

        response = requests.post(self.api_url, headers=headers, json=payload)
        ans = response.json
        print("Response: ", ans)

    def cancel_button(self, phone_number, message):
        headers = {"Authorization": self.api_token}
        payload = {"messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone_number,
                "type": "interactive",
                "interactive": {
                        "type": "button",
                        "body": {
                        "text": message
                        },
                        "action": {
                        "buttons": [
                            {
                            "type": "reply",
                            "reply": {
                                "id": "menu",
                                "title": "❌ Cancel"
                            }
                            }
                        ]
                        }
                    }
                    }
                            
                
        response = requests.post(self.api_url, headers=headers, json=payload)
        ans = response.json()

    def yes_or_no_button(self, phone_number, message):
        headers = {"Authorization": self.api_token}
        payload = {"messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone_number,
                "type": "interactive",
                "interactive": {
                        "type": "list",
                        "body": {
                        "text": message
                        },
                        "action":
                        {
                            "button": " Confirm Options",
                            "sections": [
                                {
                                    "title": "Options",
                                    "rows": [
                                        {
                                            "id": "Yes",
                                            "title": "✅ Yes",
                                        },
                                        {
                                            "id": "menu",
                                            "title": "❌ No",
                                        },
                                    ]

                                }
                            ]
                        }
                    }
                    }
                            
                
        response = requests.post(self.api_url, headers=headers, json=payload)
        ans = response.json()
        print(ans)
    
    def home_button(self, phone_number, message):
        headers = {"Authorization": self.api_token}
        payload = {"messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone_number,
                "type": "interactive",
                "interactive": {
                        "type": "button",
                        "body": {
                        "text": message
                        },
                        "action": {
                        "buttons": [
                            {
                            "type": "reply",
                            "reply": {
                                "id": "menu",
                                "title": "🔙 Menu"
                            }
                            }
                        ]
                        }
                    }
                    }
                            
                
        response = requests.post(self.api_url, headers=headers, json=payload)
        ans = response.json()

    def update_signals_subscription(self, phone_number):
        self.send_message(phone_number, "🔄 Verifying your subscription... Please wait.")
        from subscriptions.models import SubscriptionPlans, Subscribers
        user = User.objects.get(phone_number=phone_number)
        sub = Subscribers.objects.get(trader=user)
        image_file = sub.pop_image.path

        pop = self.ocr_service.process_pop_image(image_file)

        if 'error' in pop:
            self.send_signals_flow(phone_number, f"❌ OCR Error: {pop['error']}. Please resend a clearer image of your EcoCash POP.")
            return
            
        extracted_reference = pop.get('transaction_details', {}).get('reference')
        extracted_amount = pop.get('transaction_details', {}).get('amount')

        if not extracted_reference:
            message = (
                "We couldn't extract a valid Transaction ID from your message. "
                "Please resend the full EcoCash message or the correct transaction ID."
            )
            self.send_signals_flow(phone_number, message)
            return

            # Find matching cashout transaction
        cashout = CashOutTransaction.objects.filter(
                phone=sub.ecocash_number, 
                txn_id=extracted_reference
            ).first()
            
            # Try partial match if exact not found
        if not cashout:
            cashout = CashOutTransaction.objects.filter(
                phone=sub.ecocash_number, 
                txn_id__endswith=extracted_reference
            ).first()
            print("Partial match cashout:", cashout)

        if cashout:
            if cashout.completed:
                message = "This transaction was already redeemed. Please contact support if you believe this is an error."
                self.home_button(phone_number, message)

            else:
                if sub.plan.price != Decimal(extracted_amount):
                    message = f"The amount ${extracted_amount} does not match the subscription plan price of ${sub.plan.price}. Please resend the correct EcoCash POP."
                    self.send_signals_flow(phone_number, message)
                    return

                sub.active = True
                sub.expiry_date = datetime.now() + timedelta(days=sub.plan.duration_days)
                sub.save()
                
                cashout.trader = user
                cashout.save()

                message = (f"✅🎉 Congratulations! Your Trading Signals Plan Is Now Active\n\n"
                f"Plan: {sub.plan.plan_name}!\n"
                f"Amount: ${extracted_amount}\n"
                f"Duration: {sub.plan.duration_days} days\n")
                self.home_button(phone_number, message)
                return
        else:
            message = (
                "We could not find a matching EcoCash transaction for the proof of payment you provided. "
                "Please resend the proof of payment."
            )
            self.send_signals_flow(phone_number, message)
            return
    
    def create_transaction_with_ecocash_pop(self, user, amount, deriv_account_number, ecocash_number, ecocash_name, image_data):
        """Create transaction with EcoCash POP - extract only amount and reference"""
        try:
            # Calculate charge
            charge = self.calculate_charge(amount)
            
            # Create transaction
            transaction = EcoCashTransaction.objects.create(
                user=user,
                transaction_type='deposit',
                amount=amount,
                deriv_account_number=deriv_account_number,
                ecocash_number=ecocash_number,
                ecocash_name=ecocash_name,
                charge=charge,
                currency='USD',
                status='awaiting_pop'
            )
            
            # Process POP image
            pop_result = self.process_image_message(user.phone_number, image_data)
            
            if pop_result['success']:
                transaction_details = pop_result['transaction_details']
                
                # Update transaction with extracted EcoCash reference
                if transaction_details.get('reference'):
                    transaction.ecocash_reference = transaction_details['reference']
                    
                    # If we have both amount and reference, move to processing
                    if pop_result.get('is_valid', False):
                        transaction.status = 'processing'
                        transaction.description = f"Auto-extracted: ${transaction_details['amount']} | Ref: {transaction_details['reference']}"
                    else:
                        transaction.status = 'awaiting_pop'
                        transaction.admin_notes = f"OCR: {pop_result.get('validation_message', 'Incomplete extraction')}"
                    
                    transaction.save()
                
                # Create receipt record
                receipt = TransactionReceipt.objects.create(
                    transaction=transaction,
                    uploaded_by=user
                )
                
                # Save the image
                image_bytes = base64.b64decode(image_data.split(',')[1] if ',' in image_data else image_data)
                receipt.receipt_image.save(
                    f'pop_{transaction.reference_number}.jpg',
                    ContentFile(image_bytes)
                )
                
                # Store simplified OCR results
                verification_notes = [
                    f"OCR Confidence: {transaction_details.get('confidence', 0):.1%}",
                    f"Extracted Amount: {transaction_details.get('amount', 'Not found')}",
                    f"Extracted Reference: {transaction_details.get('reference', 'Not found')}",
                    f"Validation: {pop_result.get('validation_message', 'Not validated')}",
                ]
                
                receipt.verification_notes = "\n".join(verification_notes)
                receipt.save()
                
                return {
                    'success': True,
                    'transaction': transaction,
                    'extracted_amount': transaction_details.get('amount'),
                    'extracted_reference': transaction_details.get('reference'),
                    'is_valid': pop_result.get('is_valid', False),
                    'confidence': transaction_details.get('confidence', 0),
                    'message': 'EcoCash POP processed successfully'
                }
            else:
                # Fallback for OCR failure
                return self._create_manual_review_transaction(user, amount, deriv_account_number, ecocash_number, ecocash_name, image_data, pop_result)
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to process EcoCash POP: {str(e)}'
            }
    
    def _create_manual_review_transaction(self, user, amount, deriv_account_number, ecocash_number, ecocash_name, image_data, pop_result):
        """Create transaction that requires manual review"""
        charge = self.calculate_charge(amount)
        
        transaction = EcoCashTransaction.objects.create(
            user=user,
            transaction_type='deposit',
            amount=amount,
            deriv_account_number=deriv_account_number,
            ecocash_number=ecocash_number,
            ecocash_name=ecocash_name,
            charge=charge,
            currency='USD',
            status='awaiting_pop',
            admin_notes=f"OCR failed: {pop_result.get('error', 'Unknown error')}"
        )
        
        # Create receipt with image
        receipt = TransactionReceipt.objects.create(
            transaction=transaction,
            uploaded_by=user
        )
        
        image_bytes = base64.b64decode(image_data.split(',')[1] if ',' in image_data else image_data)
        receipt.receipt_image.save(
            f'pop_{transaction.reference_number}.jpg',
            ContentFile(image_bytes)
        )
        
        receipt.verification_notes = f"OCR Error: {pop_result.get('error', 'Unknown error')}"
        receipt.save()
        
        return {
            'success': True,
            'transaction': transaction,
            'extracted_amount': None,
            'extracted_reference': None,
            'is_valid': False,
            'confidence': 0,
            'message': 'Transaction created but requires manual review'
        }
    
    def get_or_create_session(self, phone_number, whatsapp_id):
        """Get existing session or create new one"""
        session, created = WhatsAppSession.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                'session_id': whatsapp_id,
                'user': self.get_or_create_user(phone_number, whatsapp_id)
            }
        )
        return session
    
    def log_message(self, phone_number, message, message_type):
        """Log WhatsApp message to database"""
        session = WhatsAppSession.objects.filter(phone_number=phone_number).first()
        if session:
            WhatsAppMessage.objects.create(
                session=session,
                message_type=message_type,
                message_body=message,
                message_from="system" if message_type == 'outgoing' else phone_number,
                message_to=phone_number if message_type == 'outgoing' else "system"
            )

    def get_or_create_user(self, phone_number, whatsapp_id):
        """Get existing user or create new one via WhatsApp"""
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                'whatsapp_id': whatsapp_id,
                'registration_source': 'whatsapp',
                'username': f"user_{phone_number}",
                'email': f"{phone_number}@supremeai.com"  # Temporary email
            }
        )
        return user
    
    def update_session_step(self, phone_number,previous_step, next_step, conversation_data=None):
        """Update user's current step in conversation"""
        session = WhatsAppSession.objects.filter(phone_number=phone_number).first()
        if session:
            session.current_step = next_step
            session.previous_step = previous_step
            if conversation_data:
                session.conversation_data.update(conversation_data)
            session.save()
    
    def calculate_charge(self, amount):
        """Calculate transaction charge for given amount"""
        return TransactionCharge.get_charge_for_amount(Decimal(str(amount)))
    
    def extract_txn_id(message):
        # Case 1: Full txn_id from message (e.g., "Txn ID: CO250714.1806.F08137")
        match = re.search(r'Txn ID[:\- ]+\s*(CO[\d\.A-Z]+)', message)
        if match:
            return match.group(1)

        # Case 2: Full txn_id only
        match = re.match(r'CO\d{6}\.\d{4}\.[A-Z0-9]+', message)
        if match:
            return match.group(0)

        # Case 3: Just the last part (e.g., F08137)
        match = re.match(r'[A-Z]\d{5}', message.strip())
        if match:
            return match.group(0)

        return None
    
    def send_sms(self, verification_code, account_number,  destination, amount):
        url = self.sms_url
        auth = self.sms_auth

        # Auto-generate messageReference & messageDate
        message_reference = uuid.uuid4().hex[:12].upper()  
        message_date = datetime.now().strftime("%Y%m%d%H%M%S")

        payload = {
            "originator": "FINPAL",
            "destination": destination,
            "messageText": f"Deriv Transfer: ${amount}. Verify if CR{account_number} is correct. Enter this code: {verification_code}. If CR is wrong, WhatsApp +263775419723. Do NOT share this code.",
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
    
    def send_deposit_flow(self, phone_number):
        headers = {"Authorization": self.api_token}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "interactive",
            "interactive" : {
            "type": "flow",
            "header": {
            "type": "text",
            "text": "DIRECT DEPOSIT"
            },
            "body": {
            "text": "Great! Let's process your Deriv deposit. Click the deposit button below to proceed."
            },
            "footer": {
            "text": "#supreme #instant #secure"
            },
            "action": {
            "name": "flow",
            "parameters": {
                "flow_message_version": "3",
                "flow_token": f"{phone_number}",
                "flow_id": "1191417283184526",
                "flow_cta": "DIRECT DEPOSIT",
                "flow_action": "navigate",
                "flow_action_payload": {
                "screen": "DETAILS",
                "data": {
                    "account_number": "account_number",
                }
                }
            }
            }
            }
         }

        response = requests.post(self.api_url, headers=headers, json=payload)
    
    def send_withdrawal_flow(self, phone_number):
        headers = {"Authorization": self.api_token}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "interactive",
            "interactive" : {
            "type": "flow",
            "header": {
            "type": "text",
            "text": "You selected Deriv Withdrawal 🏦"
            },
            "body": {
            "text": "Great! Let's process your Deriv withdrawal.\n\n Note 🔔 : We charge zero fees for withdrawals — you receive your funds with no extra costs. \n\nClick the withdrawal button below to proceed."
            },
            "footer": {
            "text": "#supreme #instant #secure"
            },
            "action": {
            "name": "flow",
            "parameters": {
                "flow_message_version": "3",
                "flow_token": f"{phone_number}",
                "flow_id": "1147957117537005",
                "flow_cta": "DERIV WITHDRAWAL",
                "flow_action": "navigate",
                "flow_action_payload": {
                "screen": "DETAILS",
                "data": {
                    "account_number": "account_number",
                }
                }
            }
            }
            }
         }

        response = requests.post(self.api_url, headers=headers, json=payload)
    
    def send_pop_flow(self, phone_number, message):
        headers = {"Authorization": self.api_token}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "interactive",
            "interactive" : {
            "type": "flow",
            "header": {
            "type": "text",
            "text": "CONFIRM DEPOSIT"
            },
            "body": {
            "text": f"{message}"
            },
            "footer": {
            "text": "#supreme #instant #secure"
            },
            "action": {
            "name": "flow",
            "parameters": {
                "flow_message_version": "3",
                "flow_token": f"{phone_number}",
                "flow_id": "25651554517790866",
                "flow_cta": "UPLOAD POP",
                "flow_action": "navigate",
                "flow_action_payload": {
                "screen": "POP",
                "data": {
                    "ecocash_pop": "ecocash_pop",
                }
                }
            }
            }
            }
         }

        response = requests.post(self.api_url, headers=headers, json=payload)
        print("Send POP Response: ", response.json())
        return
    
    def send_message_pop_flow(self, phone_number, message):
        headers = {"Authorization": self.api_token}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "interactive",
            "interactive" : {
            "type": "flow",
            "header": {
            "type": "text",
            "text": "CONFIRM DEPOSIT"
            },
            "body": {
            "text": f"{message}"
            },
            "footer": {
            "text": "#supreme #instant #secure"
            },
            "action": {
            "name": "flow",
            "parameters": {
                "flow_message_version": "3",
                "flow_token": f"{phone_number}",
                "flow_id": "1215142140476957",
                "flow_cta": "UPLOAD SMS",
                "flow_action": "navigate",
                "flow_action_payload": {
                "screen": "POP",
                "data": {
                    "ecocash_message": "ecocash_message",
                }
                }
            }
            }
            }
         }

        response = requests.post(self.api_url, headers=headers, json=payload)
        print("Send POP Response: ", response.json())
        return

    def send_signals_flow(self, phone_number, message):
        headers = {"Authorization": self.api_token}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "interactive",
            "interactive" : {
            "type": "flow",
            "header": {
            "type": "text",
            "text": "CONFIRM SIGNALS SUBSCRIPTION"
            },
            "body": {
            "text": f"{message}"
            },
            "footer": {
            "text": "#supreme #instant #secure"
            },
            "action": {
            "name": "flow",
            "parameters": {
                "flow_message_version": "3",
                "flow_token": f"{phone_number}",
                "flow_id": "1937389263504463",
                "flow_cta": "UPLOAD POP",
                "flow_action": "navigate",
                "flow_action_payload": {
                "screen": "DETAILS",
                "data": {
                    "ecocash_pop": "ecocash_pop",
                }
                }
            }
            }
            }
         }

        response = requests.post(self.api_url, headers=headers, json=payload)
        print("Send POP Response: ", response.json())
        return
        
    def create_deposit_transaction(self, fromId):
        """Create a deposit transaction using unified extraction service."""
        try:
            order = InitiateOrders.objects.get(trader__phone_number=fromId)
            trader = User.objects.get(phone_number=fromId)
            account_number = order.account_number
            ecocash_number = order.ecocash_number

            # Get the stored EcoCash POP if exists
            message_text=None
            try:
                ecocash_pop = EcocashPop.objects.get(order=order)
                if ecocash_pop.has_image:
                    image_file = ecocash_pop.ecocash_pop.path
                    has_image = True
                else:
                    message_text = ecocash_pop.ecocash_message
                    has_image = False
            except EcocashPop.DoesNotExist:
                image_file = None
                has_image = False
            
            # Use unified extraction service
            if has_image and message_text:
                # If we have both image and text, try both
                pop = self.ocr_service.extract_from_any_source(
                    image_file=image_file,
                    message=message_text
                )
            elif has_image:
                # Only image available
                pop = self.ocr_service.extract_from_any_source(image_file=image_file)
            elif message_text:
                # Only text message available
                pop = self.ocr_service.extract_from_any_source(message=message_text)
            else:
                # No image or text provided
                self.send_message_pop_flow(fromId, "❌ Please send either an EcoCash POP image or the transaction message text.")
                return
            
            # Check for extraction errors
            if 'error' in pop:
                error_msg = pop.get('error', 'Unknown error')
                if has_image:
                    self.send_message_pop_flow(fromId, f"❌ Extraction Error: {error_msg}\n\nPlease send the text cashout message instead.")
                else:
                    self.send_message_pop_flow(fromId, f"❌ Extraction Error: {error_msg}\n\nPlease resend the ecocash transaction message.")
                
                # Clean up if we created a pop object
                if has_image:
                    ecocash_pop.delete()
                return
            
            # Extract transaction details
            extracted_reference = pop.get('transaction_details', {}).get('reference')
            total_received_amount = pop.get('transaction_details', {}).get('amount')
            extraction_source = pop.get('source', 'unknown')

            print(f"Extracted txn_id: {extracted_reference} and amount: {total_received_amount} from {extraction_source}.")

            if not extracted_reference:
                message = (
                    f"We couldn't extract a valid Transaction ID from your {extraction_source}. "
                    f"Please resend the full EcoCash message.\n\n"
                    f"Extraction source: {extraction_source}"
                )
                self.send_message_pop_flow(fromId, message)
                if has_image:
                    ecocash_pop.delete()
                return
            
            # Ensure account number starts with 'CR'
            if not account_number.upper().startswith('CR'):
                account_number = 'CR' + account_number.lstrip('crCR')
            
            # Normalize phone number for lookup
            normalized_phone = ecocash_number.lstrip('0')
            if normalized_phone.startswith('263'):
                normalized_phone = normalized_phone[3:]
            
            # Look for matching cashout transaction
            cashout = CashOutTransaction.objects.filter(
                phone__in=[ecocash_number, normalized_phone, '0' + normalized_phone, 
                        '263' + normalized_phone, '+263' + normalized_phone],
                txn_id=extracted_reference
            ).first()
            
            # Try partial match if exact not found
            if not cashout:
                cashout = CashOutTransaction.objects.filter(
                    phone=ecocash_number, 
                    txn_id__endswith=extracted_reference
                ).first()
                print("Partial match cashout:", cashout)

            if cashout:
                if cashout.completed:
                    try:
                        txn = EcoCashTransaction.objects.get(
                            ecocash_number=ecocash_number,
                            ecocash_reference=cashout.txn_id,
                            status='completed'
                        )
                        credited_account = txn.deriv_account_number[:2] + '****' + txn.deriv_account_number[-3:]
                        message = (
                            f"Ooops! Sorry!\n\nThis transaction was already redeemed and credited to Deriv account: "
                            f"`{credited_account}`.\n\nIf you would like more information, please feel free to contact support.\n\nThank you!"
                        )
                        self.update_session_step(fromId, "finish_order_creation", "menu", conversation_data=None)
                        self.send_message(fromId, message)
                        return
                    except EcoCashTransaction.DoesNotExist:
                        message = (
                            "Your transaction was marked completed, but we could not find the credited account details. "
                            "Please contact support."
                        )
                    return self.send_message(fromId, message)

                else:
                    try:
                        total_amount = Decimal(cashout.amount)
                    except (ValueError, TypeError, InvalidOperation):
                        self.send_message(fromId, f"Failed to get the transaction amount from {extraction_source}. Please contact support.")
                        return
                    
                    # Calculate net amount and charge correctly
                    net_amount, charge = self._calculate_net_amount_and_charge(total_amount)
                    
                    print(f"Total received: ${total_amount}")
                    print(f"Net amount (to Deriv): ${net_amount}")
                    print(f"Transaction charge: ${charge}")
                    
                    # Validate the calculation
                    if abs((net_amount + charge) - total_amount) > Decimal('0.01'):
                        self.send_message(fromId, "Amount calculation error. Please contact support.")
                        return
                    
                    cashout.trader = trader
                    cashout.save()
                    
                    # Create the EcoCashTransaction with NET amount
                    transaction = EcoCashTransaction.objects.create(
                        user=trader,
                        transaction_type='deposit',
                        amount=net_amount,  # This is the amount that goes to Deriv
                        deriv_account_number=account_number,
                        ecocash_number=ecocash_number,
                        ecocash_name=cashout.name,
                        reference_number=f"DP{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        ecocash_reference=extracted_reference,
                        charge=charge,  
                        currency='USD',
                        status='processing',  
                    )
                    
                    # Create receipt only if we have an image
                    if has_image:
                        receipt = TransactionReceipt.objects.create(
                            transaction=transaction,
                            receipt_image=image_file,
                            uploaded_by=trader,
                            verified=True,
                            verified_at=datetime.now(),
                            verification_notes=f"Auto-verified via {extraction_source}."
                        )
                    else:
                        # Create receipt without image
                        receipt = TransactionReceipt.objects.create(
                            transaction=transaction,
                            uploaded_by=trader,
                            verified=True,
                            verified_at=datetime.now(),
                            verification_notes=f"Auto-verified via text message {extraction_source}."
                        )
                    
                    self.send_message(fromId, f"_*Processing your payment...*_")
                    
                    # Send acknowledgment message
                    source_msg = "POP image" if extraction_source == 'ocr' else "text message"
                    ack_message = (
                        f"✅ Transaction details extracted successfully from {source_msg}!\n\n"
                        f"• Amount: ${float(total_amount):.2f}\n"
                        f"• Transaction ID: {extracted_reference}\n"
                        f"• Net deposit: ${float(net_amount):.2f}\n"
                        f"• Charge: ${float(charge):.2f}\n\n"
                        f"Processing your deposit to account: {account_number}..."
                    )
                    self.send_message(fromId, ack_message)
                    
                    # Now process the deposit using DerivPaymentAgent
                    return self._process_deposit_payment(transaction, cashout, order, trader)
            else:
                message = (
                    f"We could not find a matching EcoCash transaction for the ID you provided.\n\n"
                    f"Extracted from: {extraction_source}\n"
                    f"Transaction ID: {extracted_reference}\n"
                    f"Phone: {ecocash_number}\n\n"
                    f"Please resend the full message or confirm your transaction details."
                )
                self.send_pop_flow(fromId, message)
                if has_image:
                    ecocash_pop.delete()
                return

        except InitiateOrders.DoesNotExist:
            message = "Sorry! Your order could not be found. Please start again or contact support."
            self.send_deposit_flow(fromId, message)
            if has_image:
                ecocash_pop.delete()
        except User.DoesNotExist:
            message = "Trader account not found. Please contact support."
            return self.send_message(fromId, message)

    def _calculate_net_amount_and_charge(self, total_amount):

        try:
            # First, check which charge range would apply
            charge_table = TransactionCharge.objects.filter(
                is_active=True
            ).order_by('min_amount')
            
            applicable_charge = None
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
            
            # If no range matched, use the highest percentage range as fallback
            highest_percentage = TransactionCharge.objects.filter(
                is_percentage=True,
                is_active=True
            ).order_by('-min_amount').first()
            
            if highest_percentage:
                percentage_decimal = highest_percentage.percentage_rate / Decimal('100')
                net_amount = (total_amount - highest_percentage.additional_fee) / (Decimal('1') + percentage_decimal)
                charge = total_amount - net_amount
                return net_amount.quantize(Decimal('0.01')), charge.quantize(Decimal('0.01'))
                
        except Exception as e:
            print(f"Error calculating net amount: {e}")
        
        # Fallback: use 10% + 0.9 as default
        net_amount = (total_amount - Decimal('0.90')) / Decimal('1.10')
        charge = total_amount - net_amount
        return net_amount.quantize(Decimal('0.01')), charge.quantize(Decimal('0.01'))

    def _process_deposit_payment(self, transaction, cashout, order, trader):
        """Process the actual deposit payment using DerivPaymentAgent."""
        from deriv.views import DerivPaymentAgent  
        
        # Calculate net amount
        net_amount = transaction.amount 
        
        # Initialize Deriv agent
        deriv_agent = DerivPaymentAgent()
        
        try:
            # Step 1: Fetch recipient details from Deriv (dry run)
            details_result = asyncio.run(
                deriv_agent.fetch_payment_agent_transfer_details(net_amount, transaction.deriv_account_number)
            )
            
            # Handle error response (WhatsApp URL)
            if isinstance(details_result, str) and details_result.startswith("https://wa.me/"):
                error_msg = "⚠️ Could not fetch recipient details. Please contact support."
                self._handle_transaction_failure(transaction, trader, details_result, error_msg)
                return
                
            # Check if we got valid details
            if isinstance(details_result, dict) and 'client_to_full_name' in details_result:
                deriv_name = details_result['client_to_full_name']
                local_name = cashout.name
                
                # Normalize both names
                deriv_tokens = self.normalize_name(deriv_name)
                local_tokens = self.normalize_name(local_name)
                
                # Step 2: Check if at least one token matches
                if deriv_tokens & local_tokens:
                    # ✅ Names match, process transfer
                    self._process_transfer(
                        deriv_agent, net_amount, transaction, cashout, 
                        details_result, deriv_name
                    )
                else:
                    # ❌ Name mismatch, try client verification
                    self._handle_name_mismatch(
                        deriv_agent, net_amount, transaction, cashout, 
                        details_result, deriv_name, local_name, local_tokens
                    )
            else:
                # No valid details received
                error_msg = "⚠️ Could not fetch recipient details. Please contact support."
                self._handle_transaction_failure(transaction, trader, str(details_result), error_msg)
                
        except Exception as e:
            print(f"Error processing deposit: {e}")
            error_msg = f"⚠️ Error processing transaction: {str(e)}"
            self._handle_transaction_failure(transaction, trader, str(e), error_msg)

    def _process_transfer(self, deriv_agent, net_amount, transaction, cashout, details_result, deriv_name):
        """Process the actual transfer."""
        transfer_result = asyncio.run(
            deriv_agent.create_payment_agent_transfer(net_amount, transaction.deriv_account_number)
        )
        
        error_message = "⚠️ Transfer failed. Please contact support."
        
        if isinstance(transfer_result, dict) and 'transaction_id' in transfer_result:
            # ✅ Transfer successful
            cashout.completed = True
            cashout.save()
            
            # Update EcoCashTransaction with success
            transaction.mark_deposit_completed(
                deriv_transaction_id=transfer_result.get('transaction_id'),
                notes="Deposit completed successfully via Deriv payment agent"
            )
            
            # Send success message
            obfuscated_cr = transfer_result['client_to_loginid'][:3] + '****' + transfer_result['client_to_loginid'][-2:]
            message = (
                "Transaction Successful!✅\n"
                f"Please check your Deriv Balance!\n\n"
                f"Transfer from Agent: `SupremeFx`\n\n"
                f"To Client: {transfer_result['client_to_full_name']} \n\n"
                f"Deriv Account: `{obfuscated_cr}`\n\n"
                f"Paid: `${float(transaction.amount):.2f}`\n\n"
                f"Credited: `${float(net_amount):.2f}`\n\n"
                f"Charge: `${float(transaction.charge):.2f}`\n\n"
                "For any queries, please contact our support team.\n"
                "Thank you for choosing us!"
            )
            self.send_message(transaction.user.phone_number, message)
            from .models import Switch
            switch= Switch.objects.get(transaction_type='deposit')
            if switch:
                if switch.on_message:
                    self.home_button(transaction.user.phone_number, switch.on_message)
                else:
                    pass
            return
         
        else:
            # ❌ Transfer failed
            self._handle_transfer_failure(
                transaction, transfer_result, error_message
            )

    def _handle_name_mismatch(self, deriv_agent, net_amount, transaction, cashout, 
                            details_result, deriv_name, local_name, local_tokens):
        """Handle name mismatch by checking client verification."""
        client_verification = ClientVerification.objects.filter(
            ecocash_number=transaction.ecocash_number,
            verified=True
        ).first()
        
        if client_verification:
            verified_name = client_verification.name
            verified_tokens = self.normalize_name(verified_name)
            
            if local_tokens & verified_tokens:
                # ✅ Verified name matches, process transfer
                transfer_result = asyncio.run(
                    deriv_agent.create_payment_agent_transfer(net_amount, transaction.deriv_account_number)
                )
                
                if isinstance(transfer_result, dict) and 'transaction_id' in transfer_result:
                    # Success
                    cashout.completed = True
                    cashout.save()
                    
                    # Update EcoCashTransaction
                    transaction.mark_deposit_completed(
                        deriv_transaction_id=transfer_result.get('transaction_id'),
                        notes="Deposit completed after client verification"
                    )
                    
                    # Send success message
                    obfuscated_cr = transfer_result['client_to_loginid'][:3] + '****' + transfer_result['client_to_loginid'][-2:]
                    message = (
                        "Transaction Successful!✅\n"
                        f"Please check your Deriv Balance!\n\n"
                        f"Transfer from Agent: `SupremeFx`\n\n"
                        f"To Client: {transfer_result['client_to_full_name']} \n\n"
                        f"Deriv Account: `{obfuscated_cr}`\n\n"
                        f"Paid: `${float(transaction.amount):.2f}`\n\n"
                        f"Credited: `${float(net_amount):.2f}`\n\n"
                        f"Charge: `${float(transaction.charge):.2f}`\n\n"
                        "For any queries, please contact our support team.\n"
                        "Thank you for choosing us!"
                    )
                    self.send_message(transaction.user.phone_number, message)
                    from .models import Switch
                    switch= Switch.objects.get(transaction_type='deposit')
                    if switch:
                        if switch.on_message:
                            self.home_button(transaction.user.phone_number, switch.on_message)
                        else:
                            pass
                    return
                else:
                    # Transfer failed after verification
                    self._handle_transfer_failure(
                        transaction, transfer_result, 
                        "⚠️ Transfer failed after verification. Please contact support."
                    )
                    return
        
        # Still no match → final failure
        mismatch_msg = (
            "⚠️ Name verification failed.\n\n"
            f"Deriv Account Name: {deriv_name}\n"
            f"Ecocash Registered Name: {local_name}\n\n"
            "Please Contact Support to get verified in order to make Deposits into Deriv account with different Ecocash Registered name."
        )
        self.home_button(transaction.user.phone_number, mismatch_msg)
        
        # Mark transaction as failed
        transaction.mark_failed(
            reason=f"Name verification failed. Deriv: {deriv_name}, EcoCash: {local_name}"
        )

    def _handle_transfer_failure(self, transaction, transfer_result, error_message):
        """Handle transfer failure."""
        # Check if it's a WhatsApp URL error
        if isinstance(transfer_result, str) and transfer_result.startswith("https://wa.me/"):
            import urllib.parse
            parsed_url = urllib.parse.urlparse(transfer_result)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            error_text = query_params.get("text", [""])[0]
            
            if "client's resident country is not within your portfolio" in error_text:
                error_message = (
                    "Invalid CR. Please check again and make sure that it's a Zimbabwean account. "
                    "For more information, please contact Support."
                )
            else:
                error_message = "Transfer failed. Click below to contact support:\n" + transfer_result
        
        self.home_button(transaction.user.phone_number, error_message)
        
        # Mark transaction as failed
        transaction.mark_failed(reason=f"Transfer failed: {error_message}")

    def _handle_transaction_failure(self, transaction, trader, error_details, error_message):
        """Handle general transaction failure."""
        # Send error message
        self.home_button(trader.phone_number, error_message)
        
        # Mark transaction as failed
        transaction.mark_failed(reason=f"Transaction failed: {error_details}")
    
    def normalize_name(self, name: str) -> set:
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

    def names_match(self, name1: str, name2: str) -> bool:
        """Return True if names are similar enough to allow processing."""
        n1, n2 = self.normalize_name(name1), self.normalize_name(name2)
        # Calculate similarity ratio
        ratio = SequenceMatcher(None, n1, n2).ratio()
        return ratio >= 0.75  
    
    def create_withdrawal_transaction(self, user, amount, deriv_account_number, ecocash_number, ecocash_name):
        """Create a new withdrawal transaction via WhatsApp"""
        try:
            # Calculate charge
            charge = self.calculate_charge(amount)
            
            # Create transaction
            transaction = EcoCashTransaction.objects.create(
                user=user,
                transaction_type='withdrawal',
                amount=amount,
                deriv_account_number=deriv_account_number,
                ecocash_number=ecocash_number,
                ecocash_name=ecocash_name,
                charge=charge,
                currency='USD',
                status='pending'
            )
            
            return transaction
        except Exception as e:
            print(f"Error creating withdrawal transaction: {e}")
            return None
    
    def get_user_transactions(self, user, limit=5):
        """Get user's recent transactions"""
        return EcoCashTransaction.objects.filter(user=user).order_by('-created_at')[:limit]
    
    def get_transaction_status_message(self, transaction):
        """Generate status message for a transaction"""
        status_messages = {
            'pending': '⏳ Pending',
            'awaiting_pop': '📸 Awaiting Proof of Payment',
            'processing': '🔄 Processing',
            'completed': '✅ Completed',
            'failed': '❌ Failed',
            'cancelled': '🚫 Cancelled'
        }
        
        status = status_messages.get(transaction.status, transaction.status)
        amount_info = f"${transaction.amount} (Fee: ${transaction.charge})"
        
        message = f"""
📊 *Transaction Details*

🔢 Reference: {transaction.reference_number}
💸 Amount: {amount_info}
📈 Type: {transaction.get_transaction_type_display()}
📊 Status: {status}
📅 Created: {transaction.created_at.strftime('%b %d, %Y %H:%M')}
        """
        
        if transaction.transaction_type == 'deposit' and transaction.status == 'awaiting_pop':
            message += f"""

📸 *To Complete Your Deposit:*

1. Send *${transaction.total_amount}* via EcoCash to:
   📱 *0777 123 456* (Supreme AI)

2. Take a *screenshot* of the payment confirmation

3. Reply with:
   *POP [EcoCash Reference Number]*
   And attach your screenshot

💡 *Example:* POP ABC123XYZ
"""
        
        elif transaction.transaction_type == 'withdrawal':
            message += f"""

💸 *Withdrawal Information:*
We'll process your withdrawal and send *${transaction.total_amount}* to:
📱 {transaction.ecash_number}
        """
        
        return message
    
    def format_transactions_list(self, transactions):
        """Format list of transactions for WhatsApp message"""
        if not transactions:
            return "📊 You have no transactions yet."
        
        message = "📊 *Your Recent Transactions*\n\n"
        
        for i, transaction in enumerate(transactions, 1):
            status_emoji = {
                'completed': '✅',
                'processing': '🔄', 
                'awaiting_pop': '📸',
                'pending': '⏳',
                'failed': '❌',
                'cancelled': '🚫'
            }.get(transaction.status, '📊')
            
            message += f"{i}. {status_emoji} *{transaction.reference_number}*\n"
            message += f"   💰 ${transaction.amount} ({transaction.get_transaction_type_display()})\n"
            message += f"   📊 {transaction.get_status_display()}\n"
            message += f"   📅 {transaction.created_at.strftime('%m/%d')}\n\n"
        
        message += "Type *status [reference]* for details (e.g., status ABC123456)"
        return message

    def contact_support(self, phoneNumber):
        headers = {"Authorization": settings.WHATSAPP_TOKEN}
        payload = {"messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phoneNumber,
                "type": "contacts",
                    "contacts": [{
                        "addresses": [{
                            "city": "Harare",
                            "country": "Zimbabwe",
                            "country_code": "263",
                            "type": "WORK"
                            }],
                        "emails": [{
                            "email": "frabjousafrika@gmail.com",
                            "type": "WORK"
                            },
                            ],
                        "name": {
                            "formatted_name": "SupremeFx Support",
                            "first_name": "SupremeFx",
                            "last_name": "Support",
                            "suffix": "SUFFIX",
                            "prefix": "PREFIX"
                        },
                        "org": {
                            "company": "SUPREME PVT LTD",
                            "department": "SUPPORT",
                            "title": "CUSTOMER SUPPORT"
                        },
                        "phones": [
                            {
                            "phone": "263777636820",
                            "type": "WORK",
                            "wa_id": "263777636820",
                            }],
                        "urls": [{
                            "url": "https://supreme.co.zw",
                            "type": "WORK"
                            }]
                        }]
                    }
        response = requests.post(settings.WHATSAPP_URL, headers=headers, json=payload)
        ans = response.json()
