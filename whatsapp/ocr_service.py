# whatsapp/ocr_service.py
import cv2
import pytesseract
import re
from PIL import Image
import io
import numpy as np
import logging

logger = logging.getLogger(__name__)

class EcoCashOCRService:
    """Intelligent service to extract amount and reference from EcoCash POP"""
    
    def __init__(self):
        pass
    
    def extract_text_from_image(self, image_file):
        """Extract text from image using basic OCR"""
        try:
            # Read image
            if hasattr(image_file, 'read'):
                image = Image.open(io.BytesIO(image_file.read()))
            else:
                image = Image.open(image_file)
            
            # Convert to OpenCV format
            open_cv_image = np.array(image)
            open_cv_image = open_cv_image[:, :, ::-1].copy()
            
            # Simple preprocessing - just grayscale
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
            
            # Use basic OCR configuration
            text = pytesseract.image_to_string(gray)
            
            logger.info(f"Raw OCR text: {text}")
            return text
            
        except Exception as e:
            logger.error(f"Error extracting text from image: {e}")
            return ""
    
    def extract_transaction_details(self, text):
        """Intelligently extract amount and reference - only from CashOut transactions"""
        try:
            # Just clean extra whitespace, keep everything else
            cleaned_text = ' '.join(text.split())
            
            print(f"🔍 Processing text: {cleaned_text}")
            
            # Find all CashOut transactions in the text
            cashout_transactions = self._find_cashout_transactions(cleaned_text)
            
            if not cashout_transactions:
                print("❌ No CashOut transactions found in text")
                return {'reference': None, 'amount': None, 'confidence': 0.0, 'raw_text': cleaned_text}
            
            print(f"✅ Found {len(cashout_transactions)} CashOut transaction(s)")
            
            # Take the LAST transaction (most recent one)
            last_transaction = cashout_transactions[-1]
            print(f"📊 Using last transaction: {last_transaction}")
            
            # Extract details from the selected transaction
            details = {
                'reference': self._extract_reference_from_transaction(last_transaction),
                'amount': self._extract_amount_from_transaction(last_transaction),
                'confidence': 0.0,
                'raw_text': cleaned_text,
                'transaction_count': len(cashout_transactions),
                'transaction_used': last_transaction
            }
            
            # Simple confidence calculation
            found = 0
            if details['reference']:
                found += 1
                print(f"✅ Found reference: {details['reference']}")
            else:
                print("❌ No reference found in selected transaction")
                
            if details['amount'] is not None:
                found += 1
                print(f"✅ Found amount: ${details['amount']}")
            else:
                print("❌ No amount found in selected transaction")
            
            details['confidence'] = found / 2.0
            
            return details
            
        except Exception as e:
            logger.error(f"Error extracting details: {e}")
            return {'reference': None, 'amount': None, 'confidence': 0.0, 'raw_text': text}
    
    def _find_cashout_transactions(self, text):
        """Find all CashOut transactions in the text"""
        # Split text into potential transaction blocks
        transactions = []
        
        # Look for CashOut patterns - case insensitive
        cashout_patterns = [
            r'CashOut\s*Confirmation[^.]*?USD\s*\d*\.?\d+[^.]*?Txn\s*ID[^.]*?[A-Z0-9]{2,}\.[A-Z0-9]{4,}\.[A-Z0-9]{4,}[^.]*?',
            r'CashOut[^.]*?USD\s*\d*\.?\d+[^.]*?ID[^.]*?[A-Z0-9]{2,}\.[A-Z0-9]{4,}\.[A-Z0-9]{4,}[^.]*?',
        ]
        
        for pattern in cashout_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            if matches:
                transactions.extend(matches)
                print(f"🔍 Pattern found {len(matches)} transaction(s)")
        
        # If no structured patterns found, try to split by common delimiters and find CashOut blocks
        if not transactions:
            print("🔍 No structured patterns found, trying block-based detection...")
            transactions = self._find_cashout_blocks(text)
        
        # Clean and validate transactions
        valid_transactions = []
        for transaction in transactions:
            # Check if it has the minimum required elements
            has_amount = bool(self._extract_amount_from_transaction(transaction))
            has_reference = bool(self._extract_reference_from_transaction(transaction))
            
            if has_amount or has_reference:  # At least one should be present
                valid_transactions.append(transaction)
                print(f"✅ Valid transaction block: {transaction[:100]}...")
            else:
                print(f"❌ Invalid transaction block: {transaction[:100]}...")
        
        return valid_transactions
    
    def _find_cashout_blocks(self, text):
        """Find transaction blocks by splitting text and looking for CashOut markers"""
        transactions = []
        
        # Split by common delimiters that might separate transactions
        delimiters = ['.', ';', '\n\n', 'New Wallet', 'Balance:']
        
        # First, try to find "Ecocash:" or "CashOut" as transaction starters
        blocks = re.split(r'(?=Ecocash:|CashOut)', text, flags=re.IGNORECASE)
        
        for block in blocks:
            if not block.strip():
                continue
                
            # Check if this block contains CashOut confirmation
            if re.search(r'CashOut\s*Confirmation', block, re.IGNORECASE):
                # Also check if it has amount or reference indicators
                has_amount = bool(re.search(r'USD\s*(\d*\.\d+|\d+)', block, re.IGNORECASE))
                has_reference = bool(re.search(r'Txn\s*ID|ID\s*:', block, re.IGNORECASE))
                
                if has_amount or has_reference:
                    transactions.append(block.strip())
                    print(f"✅ Found CashOut block: {block[:100]}...")
        
        return transactions
    
    def _extract_reference_from_transaction(self, transaction_text):
        """Extract reference from a single transaction block"""
        patterns = [
            r'Txn\s*ID\s*[:\-]?\s*([A-Z0-9]{2,}\.[A-Z0-9]{4,}\.[A-Z0-9]{4,})',
            r'ID\s*[:\-]?\s*([A-Z0-9]{2,}\.[A-Z0-9]{4,}\.[A-Z0-9]{4,})',
            r'([A-Z]{2}\d{6}\.\d{4}\.[A-Z]\d{5})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, transaction_text, re.IGNORECASE)
            if matches:
                ref = matches[0]
                ref = re.sub(r'\s+', '', ref)
                return ref
        
        return None
    
    def _extract_amount_from_transaction(self, transaction_text):
        """Extract amount from a single transaction block"""
        patterns = [
            r'USD\s*(\d*\.\d+|\d+)',
            r'CashOut[^0-9]*(\d*\.\d+|\d+)',
            r'CashOut\s*Confirmation[:\-]?\s*USD\s*(\d*\.\d+|\d+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, transaction_text, re.IGNORECASE)
            if matches:
                try:
                    amount = float(matches[0])
                    if 0.1 <= amount <= 10000:
                        return amount
                except ValueError:
                    continue
        
        return None
    
    def process_pop_image(self, image_file):
        """Intelligent processing - extract only from CashOut transactions"""
        try:
            print("🖼️ Starting intelligent OCR processing...")
            text = self.extract_text_from_image(image_file)
            
            if not text:
                print("❌ No text extracted")
                return {'error': 'No text could be extracted from image'}
            
            print("📝 Text extracted successfully")
            details = self.extract_transaction_details(text)
            
            is_valid = details['reference'] is not None and details['amount'] is not None
            
            # Build informative message
            if details.get('transaction_count', 0) > 0:
                if is_valid:
                    validation_msg = f"✅ Valid - Found {details['transaction_count']} CashOut transaction(s), using last one"
                else:
                    validation_msg = f"⚠️ Partial - Found {details['transaction_count']} CashOut transaction(s) but missing some data"
            else:
                validation_msg = "❌ No CashOut transactions found"
            
            return {
                'success': True,
                'is_valid': is_valid,
                'extracted_text': text,
                'transaction_details': details,
                'validation_message': validation_msg
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return {'error': str(e)}