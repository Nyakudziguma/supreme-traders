import sys
import asyncio
import os
import json
import logging
import re
import uuid
import requests
from datetime import datetime
from decimal import Decimal
from difflib import SequenceMatcher
import random
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from rest_framework.response import Response
from rest_framework import status
from deriv_api import DerivAPI, APIError
from accounts.models import User
from .models import AuthDetails
from whatsapp.models import InitiateSellOrders
from finance.models import AuditLog
from finance.models import EcoCashTransaction

logger = logging.getLogger(__name__)
TEXT_EXPO_URL = "exp://192.168.52.211:8081/--/complete-withdrawal"
BASE_EXPO_URL = "finpal://complete-withdrawal"

# Utility Functions
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

def send_sms(ecocash_number, amount, ecocash_name, destination="263785543725"):
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

async def initialize_sell_api(token, app_id):
    """
    Initialize Deriv API connection for sell operations with detailed error handling.
    
    Args:
        token: The API authorization token
        app_id: The Deriv app ID
        
    Returns:
        DerivAPI instance if successful, None otherwise
    """
    try:
        print(f" >>>>>>>>>>>>>>>>>>>>>>>>>  Received Deriv Auth API: {token[:10]}...")
        api = DerivAPI(app_id=app_id)
        
        # Ping the API
        response = await api.ping({'ping': 1})
        if not response.get('ping'):
            raise APIError("Failed to ping Deriv API")
        
        # Authorize with the token
        authorize = await api.authorize(token)
        if not authorize:
            raise APIError("Failed to authorize with API token")
        
        logger.info(f"Successfully initialized API for token: {token[:10]}...")
        return api
        
    except Exception as e:
        print("Error initializing API:", str(e))
        print(f"Type: {type(e)}")
        print(f"Repr: {repr(e)}")
        print(f"Message: {str(e)}")
        
        if hasattr(e, 'error'):
            print(f"Error code: {e.error.get('code')}")
            print(f"Error message: {e.error.get('message')}")
            print(f"Error details: {e.error.get('details')}")
        
        logging.exception("API initialization error")
        return None


class DerivPaymentAgent:
    """Class to handle Deriv API operations for payment agent transfers and withdrawals."""
    
    def __init__(self):
        self.app_id = settings.DERIV_APP_ID
        self.api_token = settings.DERIV_API_TOKEN
        self.whatsapp_number = settings.WHATSAPP_NUMBER
        
        if not self.api_token:
            sys.exit("DERIV_TOKEN environment variable is not set")
    
    def _get_whatsapp_url(self, message):
        """Helper to create WhatsApp URL with encoded message."""
        encoded_message = message.replace(" ", "%20")
        return f"https://wa.me/{self.whatsapp_number}?text={encoded_message}"
    
    async def _initialize_api(self, token=None):
        """Initialize Deriv API connection."""
        try:
            api = DerivAPI(app_id=self.app_id)
            response = await api.ping({'ping': 1})
            if not response.get('ping'):
                raise APIError("Failed to ping Deriv API")
            
            authorize_token = token if token else self.api_token
            authorize = await api.authorize(authorize_token)
            if not authorize:
                raise APIError("Failed to authorize with API token")
            
            return api
        except Exception as e:
            print(f"Error initializing API: {str(e)}")
            logging.error(f"API initialization error: {str(e)}")
            return None
    
    async def check_balance(self):
        """Check account balance."""
        api = None
        try:
            api = await self._initialize_api()
            if not api:
                return None
            
            response = await api.balance()
            balance_info = response.get('balance')
            if balance_info:
                print(f"Your current balance is {balance_info['currency']} {balance_info['balance']}")
                logging.info(f"Balance check: {balance_info['currency']} {balance_info['balance']}")
                return balance_info
            return None
        except Exception as e:
            print(f"Error checking balance: {str(e)}")
            logging.error(f"Balance check error: {str(e)}")
            return None
        finally:
            if api:
                await api.clear()
    
    async def fetch_payment_agent_transfer_details(self, amount, account_number):
        """Fetch payment agent transfer details (dry run)."""
        print(f"Fetching payment agent transfer details for amount: {amount}, account: {account_number}")
        
        api = None
        try:
            api = await self._initialize_api()
            if not api:
                return None
            
            paymentagent_transfer = {
                "paymentagent_transfer": 1,
                "amount": float(amount),
                "currency": "USD",
                "transfer_to": str(account_number).strip(),
                "dry_run": 1
            }
            
            response = await api.send(paymentagent_transfer)
            
            if response.get('error'):
                message = f"Fetch error: {response['error']['message']}"
                return self._get_whatsapp_url(message)
            
            print(f"Transfer details fetched: {response}")
            logging.info(f"Transfer details fetched: {response}")
            return response
            
        except Exception as e:
            message = f"Error fetching payment agent details: {str(e)}"
            print(message)
            return self._get_whatsapp_url(message)
        finally:
            if api:
                await api.clear()

    
    
    async def create_payment_agent_transfer(self, amount, account_number):
        """Create actual payment agent transfer."""
        api = None
        try:
            api = await self._initialize_api()
            if not api:
                return None
                        
            paymentagent_transfer = {
                "paymentagent_transfer": 1,
                "amount": float(amount),
                "currency": "USD",
                "transfer_to": str(account_number).strip()
            }
            
            response = await api.send(paymentagent_transfer)
            if response.get('error'):
                message = f"Transfer error: {response['error']['message']}"
                logger.error(message)
                return self._get_whatsapp_url(message)
            
            print(f"Transfer successful: {response}")
            logging.info(f"Transfer successful: {response}")
            return response
            
        except Exception as e:
            message = f"Error creating payment agent transfer: {str(e)}"
            print(message)
            return self._get_whatsapp_url(message)
        finally:
            if api:
                await api.clear()
    
    async def process_withdrawal(self, amount, client_loginid, code, token):
        """Process withdrawal from client User."""
        api = None
        try:
            # Use the new initialize_sell_api function for sell operations
            api = await initialize_sell_api(token, self.app_id)
            if not api:
                logger.error("Failed to initialize sell API for withdrawal")
                return {"error": "API initialization failed"}
            
            withdrawal_request = {
                "paymentagent_withdraw": 1,
                "amount": float(amount),
                "currency": "USD",
                "paymentagent_loginid": 'CR2763579',
                "description": f"Withdrawal for {client_loginid}",
                "verification_code": code,
            }
            
            response = await api.send(withdrawal_request)
            if response.get('error'):
                error_msg = f"Withdrawal error: {response['error']['message']}"
                print(error_msg)
                logging.error(error_msg)
                return {"error": error_msg}
            
            print(f"Withdrawal successful: {response}")
            logging.info(f"Withdrawal successful for client {client_loginid}: {response}")
            
            transaction_log = {
                'timestamp': datetime.now().isoformat(),
                'client_id': client_loginid,
                'amount': amount,
                'type': 'withdrawal',
                'status': 'success',
                'transaction_id': response.get('transaction_id')
            }
            logging.info(f"Transaction log: {transaction_log}")
            
            return response
            
        except Exception as e:
            error_msg = f"Error processing withdrawal: {str(e)}"
            print(error_msg)
            logging.exception("Withdrawal processing error")
            return {"error": error_msg}
        finally:
            if api:
                await api.clear()
    
    async def verify_email(self, email, amount, token, trader):
        """Send verification email for withdrawal."""
        from whatsapp.services import WhatsAppService
        service = WhatsAppService()
        
        api = None
        try:
            # Use the new initialize_sell_api function
            api = await initialize_sell_api(token, self.app_id)
            if not api:
                logger.error("API initialization failed in verify_email")
                return {"error": "API initialization failed"}
            
            verify_request = {
                "verify_email": email,
                "type": "paymentagent_withdraw",
            }
            
            response = await api.send(verify_request)
            
            print(f"verify_email response type: {type(response)}, value: {response}")
            
            # Handle string response
            if isinstance(response, str):
                print(f"API returned string error: {response}")
                return {"error": response}
            
            if isinstance(response, dict):
                if response.get('error'):
                    error_msg = f"Client verification failed: {response['error'].get('message', str(response['error']))}"
                    print(error_msg)
                    return {"error": error_msg}
                else:
                    message = "Verification link has been sent to your email. Please click the link to finish the withdrawal process"
                    service.cancel_button(trader.phone_number, message)
                    return response
            else:
                # Unexpected response type
                logger.error(f"Unexpected response type: {type(response)}")
                return {"error": f"Unexpected API response type: {type(response)}"}
            
        except Exception as e:
            error_msg = f"Error processing withdrawal: {str(e)}"
            logger.error(error_msg)
            logging.exception("Email verification error")
            return {"error": error_msg}
        finally:
            if api:
                await api.clear()

class DerivCallbackHandler:
    """Handler for Deriv API callbacks."""
    
    @staticmethod
    def redirect_with_message(message):
        """Redirect to app with message."""
        url = f"{BASE_EXPO_URL}?message={message}"
        return HttpResponse(f"""
            <html>
                <head>
                    <title>Redirecting...</title>
                    <meta http-equiv="refresh" content="0;url={url}" />
                    <script>window.location.href = "{url}";</script>
                </head>
                <body>
                    <p>Redirecting to the app...</p>
                </body>
            </html>
        """)
    
    @staticmethod
    def verify_email_callback(request):
        """Handle email verification callback for Sell orders only."""
        code = request.GET.get('code')
        account_number = request.GET.get('loginid')
        print("Retrieved account number:", account_number)
        
        from whatsapp.services import WhatsAppService
        service = WhatsAppService()
        
        if not code:
            return HttpResponseRedirect("https://wa.me/message/ITEFIG4OGBIEI1")
        
        try:
            # Get token
            token = AuthDetails.objects.get(account_number=account_number)
            print("Retrieved token:", token.token[:10] + "...")
            
            try:
                # Get order (Sell only)
                order = InitiateSellOrders.objects.get(account_number=account_number)
                trader = User.objects.get(phone_number=order.trader.phone_number)
                deriv_agent = DerivPaymentAgent()
                
                # First, fetch payment agent transfer details to get the name
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                details_result = loop.run_until_complete(
                    deriv_agent.fetch_payment_agent_transfer_details(order.amount, account_number)
                )
                
                if isinstance(details_result, dict) and 'client_to_full_name' in details_result:
                    deriv_name = details_result['client_to_full_name']
                    
                    try:
                        # Name verification
                        deriv_tokens = normalize_name(deriv_name)
                        local_tokens = normalize_name(order.ecocash_name)
                        
                        if deriv_tokens & local_tokens:
                            print("Names match:", deriv_name, order.ecocash_name)
                            # Names match - proceed with withdrawal
                            result = asyncio.run(deriv_agent.process_withdrawal(
                                order.amount, 
                                order.account_number, 
                                code, 
                                token.token
                            ))
                            
                            print("Withdrawal result:", result)
                            
                            # Check if result contains error
                            if isinstance(result, dict) and result.get('error'):
                                error_msg = result['error']
                                logger.error(f"Withdrawal failed: {error_msg}")
                                
                                # Create failed transaction
                                transaction = EcoCashTransaction.objects.create(
                                    user=order.trader,
                                    amount=order.amount,
                                    deriv_account_number=order.account_number,
                                    ecocash_number=order.ecocash_number,
                                    ecocash_name=order.ecocash_name,
                                    charge=0,
                                    reference_number=f"WD{datetime.now().strftime('%Y%m%d%H%M%S')}",
                                    transaction_type='withdrawal',
                                    status='failed',
                                )
                                
                                message = (
                                    "*⚠️ Order Processing Failed* \n\n"
                                    f"📦 Order Number: {order.account_number} \n"
                                    f"🔖 Reference Number: {transaction.reference_number} \n\n"
                                    f"Error: {error_msg}\n\n"
                                    "Please try again or contact our support team for assistance."
                                )
                                service.home_button(trader.phone_number, message)
                                order.delete()
                                return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={error_msg.replace(' ', '%20')}")
                            
                            paymentagent_transfer = result.get('paymentagent_withdraw') if result else None
                            deriv_id = result.get('transaction_id') if result else None
                            
                            if paymentagent_transfer == 1:
                                # Successful withdrawal
                                transaction = EcoCashTransaction.objects.create(
                                    user=order.trader,
                                    amount=order.amount,
                                    deriv_account_number=order.account_number,
                                    ecocash_number=order.ecocash_number,
                                    ecocash_name=order.ecocash_name,
                                    charge=0,
                                    reference_number=f"WD{datetime.now().strftime('%Y%m%d%H%M%S')}",
                                    deriv_transaction_id=deriv_id,
                                    transaction_type='withdrawal',
                                    status='completed',
                                )
                                
                                # Send SMS notification
                                clean_number = re.sub(r"\s+", "", order.ecocash_number)
                                sms_response = send_sms(clean_number, order.amount, order.ecocash_name)
                                print("SMS API Response:", sms_response)
                                
                                # Notify support staff
                                message_support = f"User {trader.phone_number} with ecocash number {order.ecocash_number} has completed a withdrawal transaction with reference {transaction.reference_number} and is now waiting for disbursement."
                                try:
                                    recipients = User.objects.filter(user_type="support")
                                    if recipients.exists():
                                        recipient = random.choice(list(recipients))
                                        # Send notification to support (implement your notification method)
                                        logger.info(f"Notification sent to support: {message_support}")
                                    else:
                                        raise User.DoesNotExist
                                except User.DoesNotExist:
                                    logger.error(f"Failed to send withdrawal notification for {transaction.reference_number}")
                                
                                message = (
                                    "🎉 Congratulations! Your Withdrawal Was Successful.\n\n"
                                    f"Your funds have been sent to your EcoCash wallet:\n\n"
                                    f"💰 Amount: ${order.amount}\n"
                                    f"📱 EcoCash Number: {order.ecocash_number}\n"
                                    f"👤 Ecocash Name: {order.ecocash_name}\n"
                                    f"🔖 Reference: {transaction.reference_number}\n\n"
                                    "Thank you for using Henry Patson Payments!\n"
                                    "If you need anything else, type MENU to return to the main menu."
                                )
                                service.home_button(trader.phone_number, message)
                                from whatsapp.models import Switch
                                switch= Switch.objects.get(transaction_type='withdrawal')
                                if switch:
                                    if switch.on_message:
                                        service.home_button(transaction.user.phone_number, switch.on_message)
                                    else:
                                        pass
                                return
                            else:
                                # Failed withdrawal
                                transaction = EcoCashTransaction.objects.create(
                                    user=order.trader,
                                    amount=order.amount,
                                    deriv_account_number=order.account_number,
                                    ecocash_number=order.ecocash_number,
                                    ecocash_name=order.ecocash_name,
                                    charge=0,
                                    reference_number=f"WD{datetime.now().strftime('%Y%m%d%H%M%S')}",
                                    transaction_type='withdrawal',
                                    status='failed',
                                )
                                
                                message = (
                                    "*⚠️ Order Processing Failed* \n\n"
                                    f"📦 Order Number: {order.account_number} \n"
                                    f"🔖 Reference Number: {transaction.reference_number} \n\n"
                                    "Please try again or contact our support team for assistance."
                                )
                                service.home_button(trader.phone_number, message)
                            
                            order.delete()
                            return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text=Withdrawal%20processed")
                        else:
                            # Names don't match
                            mismatch_msg = (
                                "⚠️ Name verification failed.\n\n"
                                f"Deriv Account Name: {deriv_name}\n"
                                f"Ecocash Registered Name: {order.ecocash_name}\n\n"
                                "Please note that we do not process third party payments. "
                                "If you believe this is an error, please contact Support."
                            )
                            service.home_button(trader.phone_number, mismatch_msg)
                            order.delete()
                            return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text=Name%20verification%20failed")
                    
                    except Exception as e:
                        print("Error during withdrawal processing:", e)
                        logger.exception("Withdrawal processing error")
                        
                        message = (
                            "*⚠️ Order Processing Failed* \n\n"
                            f"📦 Order Number: {order.account_number} \n\n"
                            f"Error: {str(e)}\n\n"
                            "Please try again or contact our support team for assistance."
                        )
                        service.home_button(trader.phone_number, message)
                        order.delete()
                        return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={str(e).replace(' ', '%20')}")
                else:
                    # Could not fetch client details
                    error_msg = "⚠️ Could not fetch Client details. Please contact support."
                    service.home_button(trader.phone_number, error_msg)
                    order.delete()
                    return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text=Could%20not%20fetch%20client%20details")
                    
            except InitiateSellOrders.DoesNotExist:
                return HttpResponseRedirect("https://wa.me/message/ITEFIG4OGBIEI1")
            except InitiateSellOrders.MultipleObjectsReturned:
                return HttpResponseRedirect("https://wa.me/message/I7ZF2KDATFXYG1")
            except Exception as e:
                message = f"Error processing order: {str(e)}"
                logger.exception("Order processing error")
                encoded = message.replace(" ", "%20")
                return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={encoded}")
                
        except AuthDetails.DoesNotExist:
            return HttpResponseRedirect("https://wa.me/message/ITEFIG4OGBIEI1")
        except AuthDetails.MultipleObjectsReturned:
            return HttpResponseRedirect("https://wa.me/message/I7ZF2KDATFXYG1")
        except Exception as e:
            message = f"An error occurred while verifying email: {str(e)}"
            logger.exception("Email verification callback error")
            encoded = message.replace(" ", "%20")
            return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={encoded}")
    
    @staticmethod
    def deriv_oauth_callback(request):
        """Handle OAuth callback from Deriv."""
        token = request.GET.get('token1')
        account = request.GET.get('acct1')
        print("OAuth callback received with token and account:", token[:10] if token else None, account)
        
        if not token:
            return JsonResponse({"error": "Failed: Invalid token"}, status=400)
        
        # Create auth details
        AuthDetails.objects.create(
            account_number=account,
            token=token,
        )
        
        try:
            order = InitiateSellOrders.objects.get(account_number=account)
            deriv_agent = DerivPaymentAgent()
            
            try:
                result = asyncio.run(deriv_agent.verify_email(
                    order.email, 
                    order.amount, 
                    token, 
                    order.trader
                ))
                
                logger.info(f"verify_email result: {result}")
                
                # Check if result is a dict
                if isinstance(result, dict):
                    if result.get('error'):
                        message = f"Verification failed: {result['error']}"
                        logger.error(message)
                        return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={message.replace(' ', '%20')}")
                    else:
                        # Success - verification email sent
                        logger.info(f"Verification email sent to {order.email}")
                        return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text=Verification%20email%20sent%20successfully")
                else:
                    # Unexpected result type
                    message = f"Unexpected result type from verify_email: {type(result)}"
                    logger.error(message)
                    return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={message.replace(' ', '%20')}")
                
            except Exception as e:
                message = f"Error initiating email verification: {str(e)}"
                logger.exception("Email verification initiation error")
                return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={message.replace(' ', '%20')}")
                
        except InitiateSellOrders.DoesNotExist:
            return HttpResponseRedirect("https://wa.me/message/ITEFIG4OGBIEI1")
        except InitiateSellOrders.MultipleObjectsReturned:
            return HttpResponseRedirect("https://wa.me/message/I7ZF2KDATFXYG1")
        except Exception as e:
            message = f"An unexpected error occurred: {str(e)}"
            logger.exception("OAuth callback error")
            return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={message.replace(' ', '%20')}")
        
        # Default fallback (should rarely be reached)
        return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}/")

# For backward compatibility
def verify_email_callback(request):
    return DerivCallbackHandler.verify_email_callback(request)

def deriv_oauth_callback(request):
    return DerivCallbackHandler.deriv_oauth_callback(request)

# Singleton instance for convenience
deriv_agent = DerivPaymentAgent()