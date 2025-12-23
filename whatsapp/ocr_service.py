import cv2
import pytesseract
import re
from PIL import Image
import io
import numpy as np
import logging
from typing import Dict, Union, BinaryIO
from .transaction_extractor import EcoCashTransactionExtractor

logger = logging.getLogger(__name__)

class EcoCashOCRService:
    """Intelligent service to extract amount and reference from EcoCash POP"""
    
    def __init__(self):
        self.text_extractor = EcoCashTransactionExtractor()
    
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
            
            logger.info(f"🔍 Processing text: {cleaned_text}")
            
            # Find all CashOut transactions in the text
            cashout_transactions = self._find_cashout_transactions(cleaned_text)
            
            if not cashout_transactions:
                logger.warning("❌ No CashOut transactions found in text")
                return {'reference': None, 'amount': None, 'confidence': 0.0, 'raw_text': cleaned_text}
            
            logger.info(f"✅ Found {len(cashout_transactions)} CashOut transaction(s)")
            
            # Take the LAST transaction (most recent one)
            last_transaction = cashout_transactions[-1]
            logger.info(f"📊 Using last transaction: {last_transaction[:100]}...")
            
            # Extract details from the selected transaction
            details = {
                'reference': self._extract_reference_from_transaction(last_transaction),
                'amount': self._extract_amount_from_transaction(last_transaction),
                'confidence': 0.0,
                'raw_text': cleaned_text,
                'transaction_count': len(cashout_transactions),
                'transaction_used': last_transaction
            }
            
            # If we didn't find reference with standard patterns, try the new format
            if not details['reference']:
                details['reference'] = self._extract_approval_code_from_transaction(last_transaction)
            
            # Simple confidence calculation
            found = 0
            if details['reference']:
                found += 1
                logger.info(f"✅ Found reference: {details['reference']}")
            else:
                logger.warning("❌ No reference found in selected transaction")
                
            if details['amount'] is not None:
                found += 1
                logger.info(f"✅ Found amount: ${details['amount']}")
            else:
                logger.warning("❌ No amount found in selected transaction")
            
            details['confidence'] = found / 2.0
            
            return details
            
        except Exception as e:
            logger.error(f"Error extracting details: {e}")
            return {'reference': None, 'amount': None, 'confidence': 0.0, 'raw_text': text}
    
    def _find_cashout_transactions(self, text):
        """Find all CashOut transactions in the text"""
        # Split text into potential transaction blocks
        transactions = []
        
        # Look for CashOut patterns - including new format
        cashout_patterns = [
            # Format 1: Your CashOut of USD X.XX from...
            r'Your CashOut[^.]*?USD\s*\d*\.?\d+[^.]*?Approval\s*Code[^.]*?[A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+[^.]*?',
            
            # Format 2: CashOut Confirmation with transaction ID
            r'CashOut\s*Confirmation[^.]*?USD\s*\d*\.?\d+[^.]*?Txn\s*ID[^.]*?[A-Z0-9]{2,}\.[A-Z0-9]{4,}\.[A-Z0-9]{4,}[^.]*?',
            
            # Format 3: Generic CashOut with ID
            r'CashOut[^.]*?USD\s*\d*\.?\d+[^.]*?ID[^.]*?[A-Z0-9]{2,}\.[A-Z0-9]{4,}\.[A-Z0-9]{4,}[^.]*?',
        ]
        
        for pattern in cashout_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            if matches:
                transactions.extend(matches)
                logger.info(f"🔍 Pattern found {len(matches)} transaction(s)")
        
        # If no structured patterns found, try to split by common delimiters and find CashOut blocks
        if not transactions:
            logger.info("🔍 No structured patterns found, trying block-based detection...")
            transactions = self._find_cashout_blocks(text)
        
        # Clean and validate transactions
        valid_transactions = []
        for transaction in transactions:
            # Check if it has the minimum required elements
            has_amount = bool(self._extract_amount_from_transaction(transaction))
            has_reference = (
                bool(self._extract_reference_from_transaction(transaction)) or
                bool(self._extract_approval_code_from_transaction(transaction))
            )
            
            if has_amount or has_reference:  # At least one should be present
                valid_transactions.append(transaction)
                logger.info(f"✅ Valid transaction block: {transaction[:100]}...")
            else:
                logger.info(f"❌ Invalid transaction block: {transaction[:100]}...")
        
        return valid_transactions
    
    def _find_cashout_blocks(self, text):
        """Find transaction blocks by splitting text and looking for CashOut markers"""
        transactions = []
        
        # Look for "Your CashOut" or "Ecocash:" or "CashOut" as transaction starters
        blocks = re.split(r'(?=Your CashOut|Ecocash:|CashOut)', text, flags=re.IGNORECASE)
        
        for block in blocks:
            if not block.strip():
                continue
                
            # Check if this block contains CashOut
            if re.search(r'CashOut', block, re.IGNORECASE):
                # For the new format, look for "Your CashOut" specifically
                if re.search(r'Your CashOut', block, re.IGNORECASE):
                    # Look for amount and approval code
                    has_amount = bool(re.search(r'USD\s*(\d*\.\d+|\d+)', block, re.IGNORECASE))
                    has_approval_code = bool(re.search(r'Approval\s*Code[:\-]?\s*[A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+', block, re.IGNORECASE))
                    
                    if has_amount or has_approval_code:
                        transactions.append(block.strip())
                        logger.info(f"✅ Found Your CashOut block: {block[:100]}...")
                else:
                    # For older formats, check for amount or reference indicators
                    has_amount = bool(re.search(r'USD\s*(\d*\.\d+|\d+)', block, re.IGNORECASE))
                    has_reference = bool(re.search(r'Txn\s*ID|ID\s*:', block, re.IGNORECASE))
                    
                    if has_amount or has_reference:
                        transactions.append(block.strip())
                        logger.info(f"✅ Found CashOut block: {block[:100]}...")
        
        return transactions
    
    def _extract_reference_from_transaction(self, transaction_text):
        """Extract reference from a single transaction block (old format)"""
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
    
    def _extract_approval_code_from_transaction(self, transaction_text):
        """Extract approval code from new format transaction block"""
        patterns = [
            r'Approval\s*Code[:\-]?\s*([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+)',
            r'Approval\s*Code[:\-]?\s*([A-Z]{2}\d{6}\.\d{4}\.[A-Z]\d{5})',
            r'Code[:\-]?\s*([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+)',
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
            # New format: "Your CashOut of USD 1.75"
            r'Your CashOut[^0-9]*USD\s*(\d*\.\d+|\d+)',
            
            # Old formats
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
            logger.info("🖼️ Starting intelligent OCR processing...")
            text = self.extract_text_from_image(image_file)
            
            if not text:
                logger.warning("❌ No text extracted from image")
                return {'error': 'No text could be extracted from image'}
            
            logger.info("📝 Text extracted successfully from image")
            details = self.extract_transaction_details(text)
            
            is_valid = details['reference'] is not None and details['amount'] is not None
            
            # Build informative message
            if details.get('transaction_count', 0) > 0:
                if is_valid:
                    validation_msg = f"✅ Valid - Found {details['transaction_count']} CashOut transaction(s), using last one"
                else:
                    validation_msg = f"⚠️ Partial - Found {details['transaction_count']} CashOut transaction(s) but missing some data"
            else:
                validation_msg = "❌ No CashOut transactions found in image"
            
            return {
                'success': True,
                'is_valid': is_valid,
                'extracted_text': text,
                'transaction_details': details,
                'validation_message': validation_msg,
                'source': 'ocr'
            }
            
        except Exception as e:
            logger.error(f"❌ OCR Error: {e}")
            return {'error': str(e), 'source': 'ocr'}
    
    def process_text_message(self, message):
        """Process text message to extract transaction details"""
        try:
            logger.info("📝 Starting text message processing...")
            return self.text_extractor.extract_from_message(message)
        except Exception as e:
            logger.error(f"❌ Text processing error: {e}")
            return {'error': str(e), 'source': 'text'}
    
    def extract_from_any_source(self, image_file=None, message=None):
        """
        Unified method to extract from image or text with fallback
        
        Args:
            image_file: Optional image file or path
            message: Optional text message
            
        Returns:
            Dictionary with extraction results
        """
        result = {
            'success': False,
            'is_valid': False,
            'details': None,
            'source': None,
            'attempts': []
        }
        
        # Try OCR from image first
        if image_file:
            logger.info("Attempting OCR extraction from image...")
            ocr_result = self.process_pop_image(image_file)
            result['attempts'].append(ocr_result)
            
            if ocr_result.get('success', False) and ocr_result.get('is_valid', False):
                logger.info("✅ OCR extraction successful")
                return self._format_result(ocr_result, 'ocr')
            
            logger.warning(f"OCR failed or partial: {ocr_result.get('validation_message', 'No message')}")
        
        # Try message extraction if OCR failed or no image provided
        if message:
            logger.info("Attempting text extraction from message...")
            text_result = self.process_text_message(message)
            result['attempts'].append(text_result)
            
            if text_result.get('success', False) and text_result.get('is_valid', False):
                logger.info("✅ Message extraction successful")
                return self._format_result(text_result, 'text')
            
            logger.warning(f"Message extraction failed or partial: {text_result.get('validation_message', 'No message')}")
        
        # If we have both attempts but neither succeeded, try to combine them
        if len(result['attempts']) >= 2:
            logger.info("Attempting to combine results from both sources...")
            combined_result = self._combine_results(result['attempts'])
            if combined_result.get('is_valid', False):
                logger.info("✅ Combined extraction successful")
                return self._format_result(combined_result, 'combined')
        
        # Nothing worked
        logger.error("All extraction methods failed")
        return self._format_failure_result(result)
    
    def _format_result(self, result, source):
        """Format successful extraction result"""
        details = result.get('transaction_details', {})
        
        return {
            'success': True,
            'is_valid': result.get('is_valid', False),
            'source': source,
            'transaction_details': {
                'reference': details.get('reference'),
                'amount': details.get('amount'),
                'confidence': details.get('confidence', 0.0),
                'raw_text': details.get('raw_text', ''),
                'pattern_matched': details.get('pattern_matched', None),
                'transaction_count': details.get('transaction_count', 1)
            },
            'validation_message': result.get('validation_message', ''),
            'extracted_text': result.get('extracted_text', '')
        }
    
    def _format_failure_result(self, result):
        """Format failed extraction result"""
        return {
            'success': False,
            'is_valid': False,
            'source': 'none',
            'transaction_details': None,
            'validation_message': 'All extraction methods failed',
            'extracted_text': '',
            'attempts': result['attempts'],
            'error': 'Could not extract transaction details from any source'
        }
    
    def _combine_results(self, attempts):
        """Combine results from multiple attempts"""
        combined = {
            'reference': None,
            'amount': None,
            'confidence': 0.0,
            'raw_text': '',
            'transaction_count': 0
        }
        
        # Collect all non-null values
        references = []
        amounts = []
        
        for attempt in attempts:
            details = attempt.get('transaction_details', {})
            if details.get('reference'):
                references.append(details['reference'])
            if details.get('amount') is not None:
                amounts.append(details['amount'])
            if details.get('raw_text'):
                combined['raw_text'] = details['raw_text']
            
            # Sum transaction counts
            combined['transaction_count'] += details.get('transaction_count', 0)
        
        # Use the most common or last value
        if references:
            combined['reference'] = references[-1]  # Use last found
        
        if amounts:
            combined['amount'] = amounts[-1]  # Use last found
        
        # Calculate combined confidence
        if combined['reference'] and combined['amount']:
            combined['confidence'] = 0.8
        elif combined['reference'] or combined['amount']:
            combined['confidence'] = 0.4
        
        return {
            'success': combined['confidence'] > 0.5,
            'is_valid': combined['reference'] is not None and combined['amount'] is not None,
            'transaction_details': combined,
            'validation_message': f"Combined results from {len(attempts)} sources",
            'source': 'combined'
        }