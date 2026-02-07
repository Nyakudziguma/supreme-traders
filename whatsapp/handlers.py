# whatsapp/handlers.py (updated)
from .services import WhatsAppService
from .models import WhatsAppSession, InitiateOrders, InitiateSellOrders, Switch, ClientVerification
from accounts.models import User
from deriv.models import AuthDetails
import re
import base64

class MessageHandler:
    def __init__(self):
        self.whatsapp_service = WhatsAppService()
    
    def handle_incoming_message(self, phone_number, message, whatsapp_id, selected_id=None, reply_data=None, payload=None):
        print(" 📩 Handling incoming message")
        print(f" From: {phone_number}, Message: {message} ")
        """Main handler for incoming WhatsApp messages"""

        # -------------------------------
        # 📌 WHITELIST +263 and +27 ONLY
        # -------------------------------
        allowed_prefixes = ["263", "27"]

        if not any(phone_number.startswith(prefix) for prefix in allowed_prefixes):
            self.whatsapp_service.send_message(
                phone_number,
                "🚫 *Access Restricted*\n\n"
                "Your number is not supported on this platform.\n\n"
                "For assistance, please contact our support team."
            )
            return

        
        # Get or create session
        session = self.whatsapp_service.get_or_create_session(phone_number, phone_number)
        
        # Check if user is blocked
        if session.user.is_blocked:
            self.whatsapp_service.send_message(phone_number, 
                "🚫 Your account has been suspended. Please contact support."
            )
            return
        
        else:
            menu_list = ['hi', 'hello', 'direct_deposit', 'deposit', 'fund_account','hey', 'menu', 'back']
            if message and message.lower() in menu_list or selected_id and selected_id in menu_list:
                self.whatsapp_service.send_menu_message(phone_number)
                self.whatsapp_service.update_session_step(phone_number, "menu","menu" ,conversation_data=None)
                return

            elif message and message.lower()=='deriv_deposit' or selected_id and selected_id=='deriv_deposit':
                switch = Switch.objects.filter(transaction_type='deposit').first()
                if not switch or not switch.is_active:
                    if switch and not switch.is_active:
                        self.whatsapp_service.send_message(phone_number, switch.off_message
                    )
                    return

                if not switch:
                    self.whatsapp_service.send_message(
                        phone_number,
                        "This service is currently unavailable."
                    )
                    return
                existing_order = InitiateOrders.objects.filter(trader=session.user).first()
                if existing_order:
                    existing_order.delete()

                self.whatsapp_service.send_deposit_flow(phone_number)
                self.whatsapp_service.update_session_step(phone_number,"menu", "direct_deposit", conversation_data=None)
                return
            
            elif message and message.lower()=='weltrade_deposit' or selected_id and selected_id=='weltrade_deposit':
                switch = Switch.objects.filter(transaction_type='weltrade_deposit').first()
                if not switch or not switch.is_active:
                    if switch and not switch.is_active:
                        self.whatsapp_service.send_message(phone_number, switch.off_message
                    )
                    return

                if not switch:
                    self.whatsapp_service.send_message(
                        phone_number,
                        "This service is currently unavailable."
                    )
                    return
                verified = ClientVerification.objects.filter(trader=session.user, verified=True).first()
                if not verified:
                    message = "🚫 Your account is not yet verified, please verify first before you can proceed"
                    self.whatsapp_service.send_message(phone_number, message)
                    self.whatsapp_service.send_verification_flow(phone_number)
                    return
                existing_order = InitiateOrders.objects.filter(trader=session.user).first()
                if existing_order:
                    existing_order.delete()

                self.whatsapp_service.send_weltrade_flow(phone_number)
                self.whatsapp_service.update_session_step(phone_number,"menu", "weltrade_deposit", conversation_data=None)
                return

            elif message and message.lower()=='withdraw' or selected_id and selected_id=='withdraw':
                switch = Switch.objects.filter(transaction_type='withdrawal').first()
                if not switch or not switch.is_active:
                    if switch and not switch.is_active:
                        self.whatsapp_service.send_message(phone_number, switch.off_message
                    )
                    return

                if not switch:
                    self.whatsapp_service.send_message(
                        phone_number,
                        "This service is currently unavailable."
                    )
                    return
                existing_withdrawal = InitiateSellOrders.objects.filter(trader=session.user).first()
                if existing_withdrawal:
                    existing_withdrawal.delete()
                self.whatsapp_service.send_withdrawal_flow(phone_number)
                self.whatsapp_service.update_session_step(phone_number,"menu", "withdrawal", conversation_data=None)
                return

            elif message and message.lower()=='signals' or selected_id and selected_id=='trading_signals':
                switch = Switch.objects.filter(transaction_type='signals').first()
                if not switch or not switch.is_active:
                    if switch and not switch.is_active:
                        self.whatsapp_service.send_message(phone_number, switch.off_message
                    )
                    return

                if not switch:
                    self.whatsapp_service.send_message(
                        phone_number,
                        "This service is currently unavailable."
                    )
                    return
                from signals.models import Subscribers
                existing_subscription = Subscribers.objects.filter(trader=session.user).first()
                if existing_subscription:
                    self.whatsapp_service.send_message(phone_number, 
                        "✅ You already have an active subscription to our trading signals, please contact support for any changes."
                    )
                    return
                self.whatsapp_service.send_signals_message(phone_number)
                self.whatsapp_service.update_session_step(phone_number,"menu", "signals", conversation_data=None)
                return
            
            elif message and message.lower()=='books' or selected_id and selected_id=='books':
                switch = Switch.objects.filter(transaction_type='books').first()
                if not switch or not switch.is_active:
                    if switch and not switch.is_active:
                        self.whatsapp_service.send_message(phone_number, switch.off_message
                    )
                    return

                if not switch:
                    self.whatsapp_service.send_message(
                        phone_number,
                        "This service is currently unavailable."
                    )
                    return
                self.whatsapp_service.send_books_message(phone_number)
                self.whatsapp_service.update_session_step(phone_number,"menu", "books", conversation_data=None)
                return
            
            elif message and message.lower()=='training' or selected_id and selected_id=='forex_training':
                switch = Switch.objects.filter(transaction_type='training').first()
                if not switch or not switch.is_active:
                    if switch and not switch.is_active:
                        self.whatsapp_service.send_message(phone_number, switch.off_message
                    )
                    return

                if not switch:
                    self.whatsapp_service.send_message(
                        phone_number,
                        "This service is currently unavailable."
                    )
                    return
                message = ("Welcome to Supreme Traders Forex Training!\n\n" 
                            "We offer a comprehensive course designed to turn you into a skilled trader.\n\n"
                            "Here’s what’s included in our package:\n\n"
                            "Strategy Mentorship: Learn proven trading strategies and risk management techniques.\n\n"
                            "Free VIP Membership: Access to exclusive signals, charts, and expert guidance.\n\n"
                            "Books & Learning Resources: Premium trading books and reference materials.\n\n"
                            "Price: $120\n\n"
                            "Please select YES to enroll or NO to return to the main menu.")
                self.whatsapp_service.yes_or_no_button(phone_number, message)
                self.whatsapp_service.update_session_step(phone_number,"menu", "training_info", conversation_data=None)
                return
            elif session.current_step == 'start_withdrawal_order':
                order= InitiateSellOrders.objects.filter(trader=session.user).first()
                if order:
                    account_number = order.account_number

                    try:
                        AuthDetails.objects.filter(account_number=account_number).delete()
                    except AuthDetails.DoesNotExist:
                        pass
                    
                    message = (
                        "Please click the login button below to login to your account "
                        "and authorize SUPREMEZW to process your withdrawal."
                    )
                    self.whatsapp_service.update_session_step(phone_number,"start_withdrawal_order", "awaiting_deriv_authentication", conversation_data=None)
                    return self.whatsapp_service.deriv_authentication(phone_number, message)

                
            elif session.current_step == 'signals' and selected_id:
                from subscriptions.models import SubscriptionPlans, Subscribers
                plan = SubscriptionPlans.objects.filter(id=selected_id).first() if selected_id else None
                if plan:
                    message = (f"You have selected the 📈 {plan.plan_name} for ${plan.price}. \n\n"
                    f"To proceed, please cashout ${plan.price} to the ecocash agent code below. \n📲 EcoCash Payment Details: \n\n"
                    f"*153 * 3 * 1 * 064550 # \n*Name:* Tashinga \n\n"
                    f"Amount: ${plan.price} \n\n"
                    f"⚠️ Please note: \n\n*Third party payments are NOT allowed.*\n\n"
                    f"Only send from the same Ecocash number you provide during subscription.\n\n"
                    f"*_Once you have made the payment, upload a screenshot of the transaction by clicking the upload pop button below._*")
                    self.whatsapp_service.send_signals_flow(phone_number, message)
                    self.whatsapp_service.update_session_step(phone_number,"signals", "waiting_for_signals_pop", conversation_data={'plan_id': plan.id})
                    Subscribers.objects.create(
                        trader=session.user,
                        plan=plan,
                        active=False,
                        expiry_date=None)
                    return
                else:
                    self.whatsapp_service.send_message(phone_number, 
                        "❌ Invalid selection. Please choose a valid subscription plan."
                    )
                    return
                
            elif message and message.lower()=='contact_support' or selected_id and selected_id=='contact_support':
                self.whatsapp_service.contact_support(phone_number)


            
            elif session.current_step == 'books' and selected_id:
                from books.models import Book
                book = Book.objects.filter(id=selected_id).first() if selected_id else None
                caption = book.description
                file_url = book.file.url
                title = book.title
                print("File path: ",file_url)
                self.whatsapp_service.send_documents(phone_number,file_url, caption, title)
                switch = Switch.objects.filter(transaction_type='books').first()
                self.whatsapp_service.send_message(phone_number, switch.on_message)
                self.whatsapp_service.update_session_step(phone_number,"menu", "menu")
                return

            elif session.current_step == 'finish_signal_subscription':
                self.whatsapp_service.update_signals_subscription(phone_number)
                self.whatsapp_service.update_session_step(phone_number,"finish_signal_subscription", "complete_signal_subscription")
                return

            elif session.current_step == 'client_verification_created':
                self.whatsapp_service.send_message(phone_number,'Your details have been recorded. Our team will be in touch with you!')
                self.whatsapp_service.update_session_step(phone_number,"menu", "menu")
                return

            elif session.current_step == 'waiting_for_ecocash_pop' and session.previous_step=='order_creation':
                order = InitiateOrders.objects.filter(trader=session.user).first()
                order_amount = order.amount if order else 'an unknown amount'
                if order.order_type == 'weltrade_deposit' and order.amount<10:
                    self.whatsapp_service.send_message(phone_number, "The minimum amount for Weltrade | Exness | HFM | USDT | etc is $10")
                    self.whatsapp_service.send_weltrade_flow(phone_number)
                    return
                
                print(" 📩 Processing Ecocash POP for amount:", order_amount, order.order_type)
                charge = self.whatsapp_service.calculate_charge(order_amount, order.order_type) if order else 0
                total_amount = round(order_amount + charge, 2) if order else 0

                message = f"Great! Here's your paymnent summary. *Check Total \n\n Deposit Amount:* ${order_amount}\n\n*Total To Pay:* ${total_amount}\n\n Payment Code: \n *153 * 3 * 1 * 064550 * Amount #\nName: Tashinga \n\nPay exact total or funds won't reflect. \n\n⚠️  Please note: \n\n*Third party payments are NOT allowed.*\n\nOnly send from the same Ecocash number you provided. \n*_Once you have made the payment, upload the a screeshot of the transaction by clicking the upload pop button below._*"
                 # Process the Ecocash POP image
                self.whatsapp_service.send_message_pop_flow(phone_number, message)
                self.whatsapp_service.update_session_step(phone_number,"waiting_for_ecocash_pop", "finish_order_creation", conversation_data=None)
                return
        
            elif session.current_step == 'finish_order_creation':
                order = InitiateOrders.objects.filter(trader=session.user).first()
                if order.order_type=='deposit':
                    self.whatsapp_service.create_deposit_transaction(phone_number)
                elif order.order_type=='weltrade_deposit':
                    self.whatsapp_service.create_weltrade_transaction(phone_number)
                self.whatsapp_service.update_session_step(phone_number,"finish_order_creation", "complete_deposit_order", conversation_data=None)
                return

            else:
                self.whatsapp_service.send_menu_message(phone_number)
                self.whatsapp_service.update_session_step(phone_number, "menu","menu" ,conversation_data=None)
                return
        