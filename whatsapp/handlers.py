# whatsapp/handlers.py (updated)
from .services import WhatsAppService
from .models import WhatsAppSession
import re
import base64

class MessageHandler:
    def __init__(self):
        self.whatsapp_service = WhatsAppService()
    
    def handle_incoming_message(self, phone_number, message, whatsapp_id, image_data=None):
        """Main handler for incoming WhatsApp messages"""
        
        # Get or create session
        session = self.whatsapp_service.get_or_create_session(phone_number, whatsapp_id)
        
        # Check if user is blocked
        if session.user.is_blocked:
            self.whatsapp_service.send_message(phone_number, 
                "🚫 Your account has been suspended. Please contact support."
            )
            return
        
        # Handle image messages (POP screenshots)
        if image_data:
            self.handle_pop_image(phone_number, session, image_data)
            return
        
        # Process text message
        message_lower = message.lower().strip()
        
        # Check for transaction-related commands
        if message_lower.startswith('deposit'):
            self.handle_deposit_start(phone_number, session, message)
        elif message_lower.startswith('withdraw'):
            self.handle_withdrawal_start(phone_number, session, message)
        elif message_lower.startswith('pop'):
            self.handle_pop_reference(phone_number, session, message)
        elif message_lower.startswith('status'):
            self.handle_transaction_status(phone_number, session, message)
        elif message_lower in ['transactions', 'history']:
            self.handle_transaction_history(phone_number, session)
        elif message_lower in ['hi', 'hello', 'hey']:
            self.handle_welcome(phone_number, session)
        elif message_lower == 'help':
            self.handle_help(phone_number, session)
        else:
            # Check if we're in a transaction flow
            if session.current_step.startswith('deposit_') or session.current_step.startswith('withdraw_'):
                self.handle_transaction_flow(phone_number, session, message)
            else:
                self.handle_unknown(phone_number, session)
    
    def handle_pop_image(self, phone_number, session, image_data):
        """Handle incoming POP screenshot - extract only amount and reference"""
        try:
            current_step = session.current_step
            
            if current_step == 'awaiting_pop_image':
                # Get stored transaction details
                amount = session.conversation_data.get('deposit_amount')
                deriv_account = session.conversation_data.get('deriv_account')
                ecocash_name = session.conversation_data.get('ecocash_name')
                
                if not all([amount, deriv_account, ecocash_name]):
                    self.whatsapp_service.send_message(phone_number,
                        "❌ Missing transaction details. Please start over with 'deposit'."
                    )
                    return
                
                # Create transaction with POP processing
                result = self.whatsapp_service.create_transaction_with_ecocash_pop(
                    user=session.user,
                    amount=amount,
                    deriv_account_number=deriv_account,
                    ecocash_number=phone_number,
                    ecocash_name=ecocash_name,
                    image_data=image_data
                )
                
                if result['success']:
                    transaction = result['transaction']
                    
                    # Reset session
                    session.current_step = 'main_menu'
                    session.conversation_data = {}
                    session.save()
                    
                    # Send appropriate confirmation message
                    if result['is_valid']:
                        message = f"""
✅ *Deposit Submitted Successfully!*

📊 Transaction: {transaction.reference_number}
💰 Amount: ${transaction.amount}
💳 Fee: ${transaction.charge}
🔢 EcoCash Ref: {result['extracted_reference']}

🤖 *Automatically Verified*
📸 POP processed successfully
🔄 Status: Processing

We'll complete your deposit shortly!
                        """
                    else:
                        message = f"""
✅ *Deposit Submitted!*

📊 Transaction: {transaction.reference_number}
💰 Amount: ${transaction.amount}
💳 Fee: ${transaction.charge}

📸 POP received
⚠️  Manual verification required
🔄 Status: Awaiting Verification

We'll verify your POP and process your deposit shortly!
                        """
                    
                    self.whatsapp_service.send_message(phone_number, message)
                    
                else:
                    self.whatsapp_service.send_message(phone_number,
                        f"❌ Failed to process deposit: {result.get('error', 'Unknown error')}"
                    )
            
            else:
                self.whatsapp_service.send_message(phone_number,
                    "📸 I received your image, but I wasn't expecting a POP right now. "
                    "Start a deposit with 'deposit' command if you want to make a transaction."
                )
                
        except Exception as e:
            self.whatsapp_service.send_message(phone_number,
                f"❌ Error processing your POP: {str(e)}"
            )
    
    def handle_deposit_flow_with_pop(self, phone_number, session, message):
        """Enhanced deposit flow with POP collection"""
        current_step = session.current_step
        
        if current_step == 'deposit_amount':
            self.handle_deposit_amount(phone_number, session, message)
        
        elif current_step == 'deposit_amount_confirmed':
            self.handle_deposit_details_for_pop(phone_number, session, message)
    
    def handle_deposit_details_for_pop(self, phone_number, session, message):
        """Handle deposit details and request POP"""
        try:
            parts = message.strip().split()
            if len(parts) < 2:
                raise ValueError("Please provide both Deriv account and EcoCash name")
            
            deriv_account = parts[0]
            ecocash_name = ' '.join(parts[1:])
            amount = session.conversation_data.get('deposit_amount')
            
            if not amount:
                raise ValueError("Amount not found. Please start over.")
            
            # Store details in session
            session.conversation_data['deriv_account'] = deriv_account
            session.conversation_data['ecocash_name'] = ecocash_name
            session.current_step = 'awaiting_pop_image'
            session.save()
            
            charge = self.whatsapp_service.calculate_charge(amount)
            total_amount = amount + charge
            
            message_text = f"""
✅ *Details Received!*

📊 Deriv Account: {deriv_account}
👤 EcoCash Name: {ecocash_name}

💸 *Payment Instructions:*

1. Send *${total_amount:.2f}* via EcoCash to:
   📱 *0777 123 456* (Supreme AI)

2. Take a *screenshot* of the payment confirmation

3. *Reply to this chat with the screenshot*

We'll automatically extract the reference and process your deposit!

💡 Make sure the screenshot shows:
• Amount: ${total_amount:.2f}
• Reference number
• Transaction details
            """
            
            self.whatsapp_service.send_message(phone_number, message_text)
            
        except Exception as e:
            self.whatsapp_service.send_message(phone_number,
                f"❌ Error: {str(e)}\n\nPlease use format: [Deriv Account] [EcoCash Name]"
            )