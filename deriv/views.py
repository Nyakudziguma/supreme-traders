import sys
import asyncio
import os
import json
import logging
from datetime import datetime
from decimal import Decimal
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

logger = logging.getLogger(__name__)

TEXT_EXPO_URL = "exp://192.168.52.211:8081/--/complete-withdrawal"
BASE_EXPO_URL = "finpal://complete-withdrawal"


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
            
            authorize_token = token or self.api_token
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
            logger.error(message)
            return self._get_whatsapp_url(message)
        finally:
            if api:
                await api.clear()
    
    async def create_payment_agent_transfer(self, amount, account_number):
        """Create actual payment agent transfer."""
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
            logger.error(message)
            return self._get_whatsapp_url(message)
        finally:
            if api:
                await api.clear()
    
    async def process_withdrawal(self, amount, client_loginid, code, token):
        """Process withdrawal from client User."""
        try:
            api = await self._initialize_api(token)
            if not api:
                return None
            
            withdrawal_request = {
                "paymentagent_withdraw": 1,
                "amount": float(amount),
                "currency": "USD",
                "paymentagent_loginid": 'CR6175985',
                "description": f"Withdrawal for {client_loginid}",
                "verification_code": code,
            }
            
            response = await api.send(withdrawal_request)
            if response.get('error'):
                print(f"Withdrawal error: {response['error']['message']}")
                logging.error(f"Withdrawal error: {response['error']['message']}")
                message = f"Withdrawal error: {response['error']['message']}"
                return self._get_whatsapp_url(message)
            
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
            print(f"Error processing withdrawal: {str(e)}")
            message = f"Error processing withdrawal: {str(e)}"
            return self._get_whatsapp_url(message)
        finally:
            if api:
                await api.clear()
    
    async def verify_email(self, email, amount, token, trader):
        from whatsapp.services import WhatsAppMessage
        service = WhatsAppMessage
        """Send verification email for withdrawal."""
        try:
            api = await self._initialize_api(token)
            if not api:
                return None
            
            verify_request = {
                "verify_email": email,
                "type": "paymentagent_withdraw",
            }
            
            response = await api.send(verify_request)
            if response.get('error'):
                print(f"Client verification failed: {response['error']['message']}")
                logging.error(f"Client verification failed: {response['error']['message']}")
                return None
            
            message = "Verification link has been sent to your email. Please click the link to finish the withdrawal process"
            service.cancel_button(trader.phone_number, message)
            
            return response
        except Exception as e:
            message = f"Error processing withdrawal: {str(e)}"
            return self._get_whatsapp_url(message)
        finally:
            if api:
                await api.clear()
    
    async def verify_app_email(self, email, amount, token, trader):
        """Send verification email for app withdrawals."""
        try:
            api = await self._initialize_api(token)
            if not api:
                return None
            
            verify_request = {
                "verify_email": email,
                "type": "paymentagent_withdraw",
            }
            
            response = await api.send(verify_request)
            if response.get('error'):
                return JsonResponse({"error": 'An error occurred while sending the verification email'}, status=400)
            
            return response
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
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
    def _handle_sell_order(order, acc, transaction, withdrawals):
        """Handle Sell order completion."""
        withdrawals.status = 'Completed'
        withdrawals.save()
        
        message = f"User {acc.trader.phone_number} with ecocash number {acc.ecocash_number} has completed a withdrawal transaction of ${acc.amount} with reference {transaction.reference} and is now waiting for disbursement."
        
        try:
            recipients = User.objects.filter(user_type="support")
            if recipients.exists():
                recipient = random.choice(recipients)
            else:
                raise User.DoesNotExist
        except User.DoesNotExist:
            AuditLog.objects.create(
                trader=acc.trader,
                action=f"Failed to send a withdrawal notification for {transaction.reference}"
            )
        
        return DerivCallbackHandler.redirect_with_message("Your withdrawal has been completed successfully. Please check your account balance.")
    
    @staticmethod
    def verify_email_callback(request):
        """Handle email verification callback."""
        from orders.helpers import handle_order
        
        code = request.GET.get('code')
        account_number = request.GET.get('loginid')
        
        if not code:
            return HttpResponseRedirect("https://wa.me/message/6VDTWBZYXSHNF1")
        
        try:
            token = AuthDetails.objects.get(account_number=account_number)
            print("Retrieved token:", token.token)
            
            try:
                order = InitiateSellOrders.objects.get(account_number=account_number)
                trader = User.objects.get(phone_number=order.trader.phone_number)
                
                # Handle different order types
                order_handlers = {
                    'Sell': lambda: handle_order(
                        trader, 'Sell', order.amount, account_number, 
                        order.email, order.ecocash_number, '', 
                        order.ecocash_name, code, token.token
                    )
                }
                
                handler = order_handlers.get(order.order_type)
                if handler:
                    handler()
                    order.delete()
                    return HttpResponseRedirect("https://wa.me/263780315552/")
                else:
                    order.delete()
                    message = 'Order type not recognized. Contact support.'
                    return HttpResponseRedirect(f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={message}")
                    
            except InitiateSellOrders.DoesNotExist:
                return HttpResponseRedirect("https://wa.me/message/IQ42HV37TTGRJ1")
            except InitiateSellOrders.MultipleObjectsReturned:
                return HttpResponseRedirect("https://wa.me/message/USODJOKF2Q7VK1")
            except Exception as e:
                message = f"Error processing order: {str(e)}"
                logger.error(message)
                encoded_message = message.replace(" ", "%20")
                return f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={encoded_message}"
                
        except AuthDetails.DoesNotExist:
            return HttpResponseRedirect("https://wa.me/message/IQ42HV37TTGRJ1")
        except AuthDetails.MultipleObjectsReturned:
            return HttpResponseRedirect("https://wa.me/message/USODJOKF2Q7VK1")
        except Exception as e:
            message = f"An error occurred while verifying email: {str(e)}"
            logger.error(message)
            encoded_message = message.replace(" ", "%20")
            return f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={encoded_message}"
    
    @staticmethod
    def deriv_oauth_callback(request):
        """Handle OAuth callback from Deriv."""
        token = request.GET.get('token1')
        account = request.GET.get('acct1')
        
        if not token:
            return JsonResponse({"error": "Failed: Invalid token"}, status=400)
        
        AuthDetails.objects.create(
            account_number=account,
            token=token,
        )
        
        try:
            order = InitiateSellOrders.objects.get(account_number=account)
        except InitiateSellOrders.DoesNotExist:
            return HttpResponseRedirect("https://wa.me/message/IQ42HV37TTGRJ1")
        except InitiateSellOrders.MultipleObjectsReturned:
            return HttpResponseRedirect("https://wa.me/message/USODJOKF2Q7VK1")
        
        # Send verification email
        deriv_agent = DerivPaymentAgent()
        asyncio.run(deriv_agent.verify_email(order.email, order.amount, token, order.trader))
        
        return HttpResponseRedirect("https://wa.me/263780315552/")


# For backward compatibility, you can keep these functions that use the new classes
def verify_app_email_callback(request):
    return DerivCallbackHandler.verify_app_email_callback(request)

def verify_email_callback(request):
    return DerivCallbackHandler.verify_email_callback(request)

def deriv_oauth_callback(request):
    return DerivCallbackHandler.deriv_oauth_callback(request)

# You can also create a singleton instance for convenience
deriv_agent = DerivPaymentAgent()