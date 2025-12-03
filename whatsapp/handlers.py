# whatsapp/handlers.py (updated)
from .services import WhatsAppService
from .models import WhatsAppSession, InitiateOrders
from accounts.models import User
import re
import base64

class MessageHandler:
    def __init__(self):
        self.whatsapp_service = WhatsAppService()
    
    def handle_incoming_message(self, phone_number, message, whatsapp_id, selected_id=None, reply_data=None, payload=None):
        print(" 📩 Handling incoming message")
        print(f" From: {phone_number}, Message: {message} ")
        """Main handler for incoming WhatsApp messages"""
        
        # Get or create session
        session = self.whatsapp_service.get_or_create_session(phone_number, whatsapp_id)
        
        # Check if user is blocked
        if session.user.is_blocked:
            self.whatsapp_service.send_message(phone_number, 
                "🚫 Your account has been suspended. Please contact support."
            )
            return
        
        else:
            if message and message.lower()=='hi':
                self.whatsapp_service.send_menu_message(phone_number)
                self.whatsapp_service.update_session_step(phone_number, "menu","menu" ,conversation_data=None)
                return
            elif message and message.lower()=='deriv_deposit' or selected_id and selected_id=='deriv_deposit':
                existing_order = InitiateOrders.objects.filter(trader=session.user).first()
                if existing_order:
                    existing_order.delete()

                self.whatsapp_service.send_deposit_flow(phone_number)
                self.whatsapp_service.update_session_step(phone_number,"menu", "direct_deposit", conversation_data=None)
                return
            elif session.current_step == 'waiting_for_ecocash_pop':
                order = InitiateOrders.objects.filter(trader=session.user).first()
                order_amount = order.amount if order else 'an unknown amount'
                print(" 📩 Processing Ecocash POP for amount:", order_amount)
                charge = self.whatsapp_service.calculate_charge(order_amount) if order else 0
                total_amount = round(order_amount + charge, 2) if order else 0

                message = f"Great! Here's your paymnent summary. *Check Total \n\n Deposit Amount:* ${order_amount}\n\n*Total To Pay:* ${total_amount}\n\n Payment Code: \n *153 * 3 * 1 * 064550 * Amount #\n\nPay exact total or funds won't reflect. \n\n⚠️  Please note: \n\n*Third party payments are NOT allowed.*\n\nOnly send from the same Ecocash number you provided. \n*_Once you have made the payment, upload the a screeshot of the transaction by clicking the upload pop button below._*"
                 # Process the Ecocash POP image
                self.whatsapp_service.send_pop_flow(phone_number, message)
                self.whatsapp_service.update_session_step(phone_number,"waiting_for_ecocash_pop", "finish_order_creation", conversation_data=None)
                return
            elif session.current_step == 'finish_order_creation':
                self.whatsapp_service.create_deposit_transaction(phone_number)
                self.whatsapp_service.update_session_step(phone_number,"finish_order_creation", "complete_deposit_order", conversation_data=None)
                return

            else:
                self.whatsapp_service.send_message(phone_number, 
                    "Thank you for your message. Our team will get back to you shortly."
                )
                return
        