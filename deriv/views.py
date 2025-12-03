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

from .models import AuthDetails
from whatsapp.models import InitiateSellOrders
from bot.messageFunctions import sendWhatsAppMessage
from bot.utils import Cancel
from api.models import Withdraw
from accounts.models import Account
from finance.models import AuditLog
from orders.views import OrderProcessor
# Import any additional helpers you need for airtime/bundle purchases
# from your_payment_processors import purchase_econet_airtime, purchase_econet_bundles, etc.

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
            sendWhatsAppMessage('263771542944', message)
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
                sendWhatsAppMessage('263771542944', message)
                return self._get_whatsapp_url(message)
            
            print(f"Transfer successful: {response}")
            logging.info(f"Transfer successful: {response}")
            return response
            
        except Exception as e:
            message = f"Error creating payment agent transfer: {str(e)}"
            sendWhatsAppMessage('263771542944', message)
            return self._get_whatsapp_url(message)
        finally:
            if api:
                await api.clear()
    
    async def process_withdrawal(self, amount, client_loginid, code, token):
        """Process withdrawal from client account."""
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
            Cancel(trader.phone_number, message)
            
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
    def verify_app_email_callback(request):
        """Handle app email verification callback."""
        code = request.GET.get('code')
        account_number = request.GET.get('loginid')
        
        try:
            acc = Withdraw.objects.get(account_number=account_number)
        except Withdraw.DoesNotExist:
            return DerivCallbackHandler.redirect_with_message("Account not found for withdrawal")
        
        try:
            order = OrderProcessor.initiate_transaction(
                acc.trader,
                order_type=acc.order_type,
                amount=acc.amount,
                account_number=account_number,
                ecocash_number=acc.ecocash_number,
                ecocash_name=acc.ecocash_name
            )
            
            if not order:
                return DerivCallbackHandler.redirect_with_message("An error occurred while creating your withdrawal order")
            
            # Process withdrawal
            deriv_agent = DerivPaymentAgent()
            try:
                withdrawal_response = asyncio.run(
                    deriv_agent.process_withdrawal(acc.amount, account_number, code, acc.token)
                )
            except Exception as e:
                OrderProcessor.process_order(order.id, 'Failed')
                return DerivCallbackHandler.redirect_with_message(f"An error occurred during withdrawal: {e}")
            
            if withdrawal_response.get('paymentagent_withdraw') != 1:
                OrderProcessor.process_order(order.id, 'Failed')
                return DerivCallbackHandler.redirect_with_message("Withdrawal initiation failed")
            
            OrderProcessor.process_order(order.id, 'Completed')
            
            # Create transaction and handle different order types
            return DerivCallbackHandler._handle_order_completion(order, acc, withdrawal_response)
            
        except ValidationError as e:
            return DerivCallbackHandler.redirect_with_message(f"Validation Error: {e}")
        except Exception as e:
            return DerivCallbackHandler.redirect_with_message(f"Unexpected Error: {e}")
    
    @staticmethod
    def _handle_order_completion(order, acc, withdrawal_response):
        """Handle completion of different order types."""
        try:
            deriv_id = withdrawal_response.get('transaction_id')
            extras = json.dumps(withdrawal_response)
            
            with db_transaction.atomic():
                charge = order.charge
                
                transaction = Transaction.objects.create(
                    order=order,
                    trader=acc.trader,
                    transaction_type=order.order_type,
                    amount=order.amount,
                    charge=charge,
                    status='Successful',
                    deriv_id=deriv_id,
                    extras=extras
                )
                
                withdrawals = Withdrawals.objects.create(
                    trader=acc.trader,
                    transaction=transaction,
                    amount=acc.amount
                )
                
                AuditLog.objects.create(
                    trader=acc.trader,
                    action=f"Transaction ID {transaction.id} for ${acc.amount} was completed successfully."
                )
                
                # Handle different order types
                order_type_handlers = {
                    'Sell': DerivCallbackHandler._handle_sell_order,
                    'Econet_Airtime': DerivCallbackHandler._handle_econet_airtime,
                    'Econet_Bundles': DerivCallbackHandler._handle_econet_bundles,
                    'Netone_Bundles': DerivCallbackHandler._handle_netone_bundles,
                }
                
                handler = order_type_handlers.get(order.order_type)
                if handler:
                    return handler(order, acc, transaction, withdrawals)
                else:
                    return DerivCallbackHandler.redirect_with_message("Unknown order type")
                
        except Exception as e:
            with db_transaction.atomic():
                transaction = Transaction.objects.create(
                    order=order,
                    trader=acc.trader,
                    transaction_type=order.order_type,
                    amount=acc.amount,
                    charge=order.charge,
                    status='Failed',
                    extras=json.dumps({"error": str(e)})
                )
                AuditLog.objects.create(
                    trader=acc.trader,
                    action=f"Transaction {transaction.id} failed. Error: {str(e)}"
                )
            
            return DerivCallbackHandler.redirect_with_message("An error occurred while processing your withdrawal")
    
    @staticmethod
    def _handle_sell_order(order, acc, transaction, withdrawals):
        """Handle Sell order completion."""
        withdrawals.status = 'Completed'
        withdrawals.save()
        
        message = f"User {acc.trader.phone_number} with ecocash number {acc.ecocash_number} has completed a withdrawal transaction of ${acc.amount} with reference {transaction.reference} and is now waiting for disbursement."
        
        try:
            recipients = Account.objects.filter(user_type="support")
            if recipients.exists():
                recipient = random.choice(recipients)
                OrderProcessor.create_notification(recipient, message, transaction)
            else:
                raise Account.DoesNotExist
        except Account.DoesNotExist:
            AuditLog.objects.create(
                trader=acc.trader,
                action=f"Failed to send a withdrawal notification for {transaction.reference}"
            )
        
        return DerivCallbackHandler.redirect_with_message("Your withdrawal has been completed successfully. Please check your account balance.")
    
    @staticmethod
    def _handle_econet_airtime(order, acc, transaction, withdrawals):
        """Handle Econet airtime purchase."""
        withdrawals.status = 'Completed'
        withdrawals.save()
        
        payload = {
            "amount": float(order.amount),
            "target_mobile": acc.RechargeAccount,
        }
        
        try:
            # You'll need to implement or import these functions
            from your_payment_processors import purchase_econet_airtime, fetch_account_balance
            
            response_data = purchase_econet_airtime(payload)
            
            if response_data.get("status") == "success":
                message = f"{response_data['message']} topped up account {acc.RechargeAccount} with {order.amount}"
                
                balance_response = fetch_account_balance("0137106121109")
                if balance_response.get("status") == "success":
                    vendor_balance = balance_response.get("vendorBalance")
                    balance_message = f"Airtime purchase Successful. Your new vendor balance is: {vendor_balance}"
                else:
                    balance_message = "Balance retrieval failed."
                
                AuditLog.objects.create(
                    trader=order.trader,
                    action=f"Transaction with ID {transaction.id} for {order.amount} for Econet Airtime."
                )
                sendWhatsAppMessage("0786976684", balance_message)
                return DerivCallbackHandler.redirect_with_message(f"{message}")
            
            else:
                message = response_data.get("message", "Transaction failed")
                notification = f"Failed to purchase airtime of ${order.amount} with reference number {order.reference_number}. Please check it out."
                DerivCallbackHandler._send_support_notification(notification, transaction)
                return DerivCallbackHandler.redirect_with_message(f"{message}")
                
        except Exception as e:
            print(f"Error processing airtime purchase: {e}")
            message = "Error processing your airtime purchase. Please try again."
            return DerivCallbackHandler.redirect_with_message(f"{message}")
    
    @staticmethod
    def _handle_econet_bundles(order, acc, transaction, withdrawals):
        """Handle Econet bundles purchase."""
        withdrawals.status = 'Completed'
        withdrawals.save()
        
        try:
            payload = {
                "target_mobile": acc.RechargeAccount,
                "productCode": acc.productCode,
            }
            
            # You'll need to implement or import these functions
            from your_payment_processors import purchase_econet_bundles, fetch_account_balance
            
            response_data = purchase_econet_bundles(payload)
            
            if response_data.get("data", {}).get("responseCode") in ["00", "000"]:
                message = f"Bundle Purchase successful. Topped up account {acc.RechargeAccount} with US${order.amount} mobile data from Deriv"
                
                balance_response = fetch_account_balance("0137106121109")
                if balance_response.get("status") == "success":
                    vendor_balance = balance_response.get("vendorBalance")
                    balance_message = f"Airtime purchase Successful. Your new vendor balance is: {vendor_balance}"
                else:
                    balance_message = "Balance retrieval failed."
                
                sendWhatsAppMessage("0786976684", balance_message)
                AuditLog.objects.create(
                    trader=order.trader,
                    action=f"Transaction with ID {transaction.id} for {order.amount} for Econet Bundles."
                )
                return DerivCallbackHandler.redirect_with_message(f"{message}")
            
            else:
                message = response_data.get("message", "Transaction failed")
                notification = f"Failed to purchase Econet bundles of ${order.amount} with reference number {order.reference_number}. Please check it out."
                DerivCallbackHandler._send_support_notification(notification, transaction)
                return DerivCallbackHandler.redirect_with_message(f"{message}")
                
        except Exception as e:
            print(f"Error processing bundle purchase: {e}")
            message = "Error processing your bundle purchase. Please try again."
            return DerivCallbackHandler.redirect_with_message(f"{message}")
    
    @staticmethod
    def _handle_netone_bundles(order, acc, transaction, withdrawals):
        """Handle NetOne bundles purchase."""
        withdrawals.status = 'Completed'
        withdrawals.save()
        
        payload = {
            "amount": int(order.amount),
            "target_mobile": order.RechargeAccount,
            "productCode": order.productCode,
        }
        
        try:
            # You'll need to implement or import these functions
            from your_payment_processors import purchase_netone_airtime, fetch_account_balance, resend_transaction_lookup
            
            response_data = purchase_netone_airtime(payload)
            
            if response_data.get("data", {}).get("responseCode") in ["00", "000"]:
                message = f"{response_data.get('message', 'Success')} topped up account {acc.RechargeAccount} with US${acc.amount} airtime from Deriv"
                
                balance_response = fetch_account_balance("0137106121109")
                if balance_response.get("status") == "success":
                    vendor_balance = balance_response.get("vendorBalance")
                    balance_message = f"Airtime purchase Successful. Your new vendor balance is: {vendor_balance}"
                else:
                    balance_message = "Balance retrieval failed."
                
                sendWhatsAppMessage("0786976684", balance_message)
                return DerivCallbackHandler.redirect_with_message(f"{message}")
            
            elif response_data.get("data", {}).get("responseCode") in ["09", "009"]:
                lookup_result = resend_transaction_lookup(response_data["data"].get("originalReference"))
                
                if lookup_result and lookup_result.get("response_code") == '00':
                    message = f"Your airtime top-up was successfully processed for {acc.RechargeAccount}."
                    return DerivCallbackHandler.redirect_with_message(f"{message}")
                elif lookup_result and lookup_result.get("response_code") == '09':
                    message = "Your transaction is still being processed. Please wait while we retry."
                    return DerivCallbackHandler.redirect_with_message(f"{message}")
                else:
                    retry_response = purchase_netone_airtime(payload)
                    if retry_response["status"] == "success" and retry_response["data"]["responseCode"] == '00':
                        message = f"Purchase successful! Airtime of ${order.amount} credited to {acc.RechargeAccount}."
                    else:
                        message = "Airtime Purchase failed. Please contact support."
                    return DerivCallbackHandler.redirect_with_message(f"{message}")
            
            else:
                message = response_data.get("message", "Transaction failed")
                notification = f"Failed to purchase NetOne airtime of ${order.amount} with reference number {order.reference_number}. Please check it out."
                DerivCallbackHandler._send_support_notification(notification, transaction)
                return DerivCallbackHandler.redirect_with_message(f"{message}")
                
        except Exception as e:
            print(f"Error processing airtime purchase: {e}")
            message = "Error processing your airtime purchase. Please try again."
            return DerivCallbackHandler.redirect_with_message(f"{message}")
    
    @staticmethod
    def _send_support_notification(message, transaction):
        """Send notification to support staff."""
        try:
            recipients = list(Account.objects.filter(user_type="support"))
            if recipients:
                recipient = random.choice(recipients)
                OrderProcessor.create_notification(recipient, message, transaction)
            else:
                raise Account.DoesNotExist
        except Account.DoesNotExist:
            AuditLog.objects.create(
                trader=transaction.trader,
                action=message
            )
    
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
                trader = Trader.objects.get(phone_number=order.trader.phone_number)
                
                # Handle different order types
                order_handlers = {
                    'Sell': lambda: handle_order(
                        trader, 'Sell', order.amount, account_number, 
                        order.email, order.ecocash_number, '', 
                        order.ecocash_name, code, token.token
                    ),
                    'Econet_Airtime': lambda: handle_order(
                        trader, order.order_type, order.amount, account_number, 
                        order.email, '', '', '', code, token.token, 
                        order.Merchant, order.RechargeAccount
                    ),
                    'Econet_Bundles': lambda: handle_order(
                        trader, order.order_type, order.amount, account_number, 
                        order.email, '', '', '', code, token.token, 
                        order.Merchant, order.RechargeAccount, order.productCode
                    ),
                    'Netone_Bundles': lambda: handle_order(
                        trader, order.order_type, order.amount, account_number, 
                        order.email, '', '', '', code, token.token, 
                        order.Merchant, order.RechargeAccount, order.productCode
                    ),
                    'Telone_Bundles': lambda: handle_order(
                        trader, order.order_type, order.amount, account_number, 
                        order.email, '', '', '', code, token.token, 
                        order.Merchant, order.RechargeAccount, order.productCode
                    ),
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
                sendWhatsAppMessage('263771542944', message)
                encoded_message = message.replace(" ", "%20")
                return f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={encoded_message}"
                
        except AuthDetails.DoesNotExist:
            return HttpResponseRedirect("https://wa.me/message/IQ42HV37TTGRJ1")
        except AuthDetails.MultipleObjectsReturned:
            return HttpResponseRedirect("https://wa.me/message/USODJOKF2Q7VK1")
        except Exception as e:
            message = f"An error occurred while verifying email: {str(e)}"
            sendWhatsAppMessage('263771542944', message)
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