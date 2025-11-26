# whatsapp/services.py (updated)
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from accounts.models import User
from finance.models import EcoCashTransaction, TransactionReceipt, TransactionCharge
from .models import WhatsAppSession, WhatsAppMessage
from .ocr_service import EcoCashOCRService
from decimal import Decimal
import base64
import io

class WhatsAppService:
    def __init__(self):
        self.api_url = settings.WHATSAPP_API_URL
        self.api_token = settings.WHATSAPP_API_TOKEN
        self.ocr_service = EcoCashOCRService()
    
    def send_message(self, phone_number, message):
        """Send message via WhatsApp API"""
        try:
            payload = {
                'phone': phone_number,
                'message': message,
                'token': self.api_token
            }
            response = requests.post(f"{self.api_url}/send", json=payload)
            response.raise_for_status()
            
            # Log the outgoing message
            self.log_message(phone_number, message, 'outgoing')
            return True
            
        except Exception as e:
            print(f"Failed to send WhatsApp message: {e}")
            return False
    
    def process_image_message(self, phone_number, image_data, mime_type=None):
        """Process incoming image message (POP screenshot)"""
        try:
            # Convert base64 image data to file-like object
            if isinstance(image_data, str) and image_data.startswith('data:'):
                # Data URL format: data:image/png;base64,...
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            image_file = io.BytesIO(image_bytes)
            
            # Process image with OCR
            result = self.ocr_service.process_pop_image(image_file)
            
            if 'error' in result:
                return {
                    'success': False,
                    'error': result['error']
                }
            
            return {
                'success': True,
                'extracted_text': result.get('extracted_text', ''),
                'transaction_details': result.get('transaction_details', {})
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to process image: {str(e)}'
            }
    
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