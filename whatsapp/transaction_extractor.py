import re
import logging
from typing import Dict
from datetime import timedelta


logger = logging.getLogger(__name__)

class EcoCashTransactionExtractor:
    """Service to extract transaction details from text messages"""
    
    def extract_from_message(self, message: str) -> Dict:
        """
        Extract transaction details from an EcoCash message
        
        Args:
            message: Text message containing transaction details
            
        Returns:
            Dictionary with extracted details
        """
        try:
            cleaned_message = self._clean_message(message)
            logger.info(f"Processing message: {cleaned_message}")
            
            # First try to extract from the cleaned message
            details = self._extract_from_cleaned_message(cleaned_message)
            
            # If unsuccessful, try with the original message
            if not details['reference'] or not details['amount']:
                details = self._extract_from_original_message(message)
            
            # Calculate confidence
            confidence = self._calculate_confidence(details)
            details['confidence'] = confidence
            
            return {
                'success': confidence > 0.3,  # 30% threshold
                'is_valid': details['reference'] is not None and details['amount'] is not None,
                'extracted_text': message,
                'transaction_details': details,
                'validation_message': self._generate_validation_message(details, confidence),
                'source': 'message'
            }
            
        except Exception as e:
            logger.error(f"Error extracting from message: {e}")
            return {
                'success': False,
                'error': str(e),
                'source': 'message'
            }
    
    def _clean_message(self, message: str) -> str:
        """Clean and normalize the message text"""
        # Replace multiple spaces with single space
        message = re.sub(r'\s+', ' ', message)
        
        # Remove special characters but keep dots and colons for patterns
        message = re.sub(r'[^\w\s\.\:\-\$]', ' ', message)
        
        # Clean up any remaining extra spaces
        message = ' '.join(message.split())
        
        return message.strip()
    
    def _extract_from_cleaned_message(self, message: str) -> Dict:
        """Extract details from cleaned message using multiple patterns"""
        details = {
            'reference': None,
            'amount': None,
            'raw_text': message,
            'source': 'cleaned_message',
            'transaction_count': 1
        }
        
        # Pattern 1: Ecocash: CashOut Confirmation: USD 190 to 057935- LONELY MUUSHA.Txn ID :CO251113.0614.F36867.
        pattern1 = r'Ecocash:\s*CashOut\s*Confirmation:\s*USD\s*(\d+(?:\.\d+)?)\s*.*?Txn\s*ID\s*:\s*([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+)'
        
        # Pattern 2: Your CashOut of USD 1.75 from 123456. Approval Code: AB123456.7890.C12345
        pattern2 = r'Your\s*CashOut\s*of\s*USD\s*(\d+(?:\.\d+)?)\s*.*?Approval\s*Code[:\s]*([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+)'
        
        # Pattern 3: CashOut Confirmation: USD X.XX Txn ID: XXX.XXXX.XXXXX
        pattern3 = r'CashOut\s*Confirmation[:\s]*USD\s*(\d+(?:\.\d+)?)\s*.*?Txn\s*ID[:\s]*([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+)'
        
        # Pattern 4: Generic pattern with USD amount and reference
        pattern4 = r'USD\s*(\d+(?:\.\d+)?)\s*.*?(?:Txn\s*ID|ID|Approval\s*Code|Code)[:\s]*([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+)'
        
        patterns = [
            (pattern1, 'pattern1'),
            (pattern2, 'pattern2'),
            (pattern3, 'pattern3'),
            (pattern4, 'pattern4')
        ]
        
        for pattern, pattern_name in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                logger.info(f"Matched {pattern_name}")
                details['amount'] = float(match.group(1))
                details['reference'] = match.group(2).strip()
                details['pattern_matched'] = pattern_name
                break
        
        return details
    
    def _extract_from_original_message(self, original_message: str) -> Dict:
        """Fallback extraction from original message using more flexible patterns"""
        details = {
            'reference': None,
            'amount': None,
            'raw_text': original_message,
            'source': 'original_message',
            'transaction_count': 1
        }
        
        # Try to extract amount using various patterns
        amount_patterns = [
            r'USD\s*(\d+(?:\.\d+)?)',
            r'\$\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*USD'
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, original_message, re.IGNORECASE)
            if match:
                try:
                    details['amount'] = float(match.group(1))
                    break
                except ValueError:
                    continue
        
        # Try to extract reference using various patterns
        reference_patterns = [
            r'Txn\s*ID[:\s]*([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+)',
            r'ID[:\s]*([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+)',
            r'Approval\s*Code[:\s]*([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+)',
            r'Code[:\s]*([A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+)',
            r'([A-Z]{2}\d{6}\.\d{4}\.[A-Z]\d{5})',
            r'([A-Z0-9]{2,}\.[A-Z0-9]{4,}\.[A-Z0-9]{4,})'
        ]
        
        for pattern in reference_patterns:
            match = re.search(pattern, original_message, re.IGNORECASE)
            if match:
                details['reference'] = match.group(1).strip()
                break
        
        return details
    
    def _calculate_confidence(self, details: Dict) -> float:
        """Calculate confidence score for extraction"""
        confidence = 0.0
        
        if details['amount'] is not None:
            confidence += 0.5
        
        if details['reference'] is not None:
            confidence += 0.5
            
            # Extra confidence for well-formed references
            if re.match(r'^[A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+$', details['reference']):
                confidence += 0.2
        
        return min(confidence, 1.0)  # Cap at 1.0
    
    def _generate_validation_message(self, details: Dict, confidence: float) -> str:
        """Generate validation message based on extraction results"""
        if confidence >= 0.9:
            return f"✅ Excellent - Extracted amount: ${details['amount']}, reference: {details['reference']}"
        elif confidence >= 0.7:
            return f"✅ Good - Extracted amount: ${details['amount']}, reference: {details['reference']}"
        elif confidence >= 0.5:
            return f"⚠️ Partial - Found {'amount' if details['amount'] else ''}{' and ' if details['amount'] and details['reference'] else ''}{'reference' if details['reference'] else ''}"
        elif confidence > 0:
            return f"⚠️ Low confidence - Partial extraction"
        else:
            return "❌ No transaction details found in message"