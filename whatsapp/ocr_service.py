# whatsapp/ocr_service.py
import cv2
import pytesseract
import re
from PIL import Image
import io
import numpy as np
import logging
import signal
import time
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor
import asyncio

logger = logging.getLogger(__name__)

class TimeoutException(Exception):
    """Custom exception for timeout handling"""
    pass

class EcoCashOCRService:
    """Intelligent service to extract amount and reference from EcoCash POP with timeout protection"""
    
    def __init__(self, timeout_seconds=30):
        self.timeout_seconds = timeout_seconds
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.ocr_timeout = 15  # OCR-specific timeout (shorter than total)
        
    def _timeout_handler(self, signum, frame):
        """Signal handler for timeout"""
        raise TimeoutException(f"OCR processing timeout after {self.timeout_seconds} seconds")
    
    def extract_text_from_image(self, image_file):
        """Extract text from image using optimized OCR with size validation"""
        temp_file = None
        
        try:
            start_time = time.time()
            
            # Validate file size before processing
            if hasattr(image_file, 'read'):
                if hasattr(image_file, 'seek'):
                    image_file.seek(0, 2)  # Go to end
                    file_size = image_file.tell()
                    image_file.seek(0)  # Reset to beginning
                    
                    if file_size > 5 * 1024 * 1024:  # 5MB limit (reduced from 10MB)
                        print(f"⚠️ File too large: {file_size/1024/1024:.2f}MB, resizing...")
                        # We'll handle this in preprocessing
                    elif file_size < 1024:  # 1KB minimum
                        print(f"⚠️ File too small: {file_size} bytes")
                        return ""
            
            # Read image
            if hasattr(image_file, 'read'):
                image_bytes = image_file.read()
                image_file.seek(0)  # Reset for potential retry
                image = Image.open(io.BytesIO(image_bytes))
            else:
                image = Image.open(image_file)
            
            print(f"📏 Image loaded: {image.size[0]}x{image.size[1]}, mode: {image.mode}")
            
            # Convert to RGB if necessary (important for OCR)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save to temporary file (sometimes helps with Tesseract)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                temp_file = tmp.name
                image.save(tmp.name, 'PNG', optimize=True)
            
            # Convert to OpenCV format from file (more reliable)
            open_cv_image = cv2.imread(temp_file)
            
            if open_cv_image is None:
                print("❌ Failed to load image with OpenCV, trying direct conversion...")
                # Fallback to direct conversion
                open_cv_image = np.array(image)
                open_cv_image = open_cv_image[:, :, ::-1].copy()
            
            # DEBUG: Save processed image for inspection
            debug_dir = "debug_ocr"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            debug_path = os.path.join(debug_dir, f"debug_{int(time.time())}.png")
            
            # Optimize image preprocessing
            print("🔄 Preprocessing image...")
            
            # Convert to grayscale
            if len(open_cv_image.shape) == 3:
                gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
            else:
                gray = open_cv_image
            
            # Resize if too large or too small (Tesseract works best with certain sizes)
            height, width = gray.shape
            print(f"📐 Grayscale image: {width}x{height}")
            
            # Optimal size for Tesseract is 300 DPI, but we'll resize for consistency
            target_height = 1500  # Good balance for readability
            if height > 2500 or height < 500:
                scale = target_height / height
                new_width = int(width * scale)
                new_height = target_height
                gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
                print(f"📏 Resized to: {new_width}x{new_height}")
            
            # Apply preprocessing steps
            print("🔄 Applying preprocessing...")
            
            # 1. Denoising (light)
            gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            
            # 2. Increase contrast
            gray = cv2.equalizeHist(gray)
            
            # 3. Apply Gaussian blur to reduce noise
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # 4. Adaptive thresholding
            gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY, 11, 2)
            
            # Save debug image
            cv2.imwrite(debug_path, gray)
            print(f"💾 Debug image saved: {debug_path}")
            
            # Try different OCR configurations
            print("🔍 Running OCR...")
            
            # Configuration 1: Basic (fastest)
            configs = [
                '--oem 1 --psm 6',  # OEM 1 = Neural nets LSTM only, PSM 6 = Assume uniform block
                '--oem 3 --psm 6',  # OEM 3 = Default, PSM 6 = Assume uniform block
                '--oem 1 --psm 3',  # PSM 3 = Fully automatic page segmentation
                '--oem 1 --psm 4',  # PSM 4 = Assume single column of text
            ]
            
            text = ""
            best_text = ""
            
            for i, config in enumerate(configs[:2]):  # Try first 2 configs only
                try:
                    print(f"  Trying config {i+1}: {config}")
                    config_start = time.time()
                    
                    # Use pytesseract with explicit timeout
                    text = pytesseract.image_to_string(
                        gray, 
                        config=config, 
                        timeout=self.ocr_timeout
                    )
                    
                    config_time = time.time() - config_start
                    print(f"    Config {i+1} completed in {config_time:.2f}s, got {len(text)} chars")
                    
                    if len(text.strip()) > len(best_text.strip()):
                        best_text = text
                        print(f"    Config {i+1} gave better results")
                    
                    # If we got decent text, break early
                    if len(text.strip()) > 20:
                        print(f"✅ Good text found with config {i+1}, stopping")
                        break
                        
                except pytesseract.TesseractError as e:
                    print(f"    Config {i+1} error: {e}")
                    continue
                except Exception as e:
                    print(f"    Config {i+1} unexpected error: {e}")
                    continue
            
            # Use the best text we found
            if best_text:
                text = best_text
            
            processing_time = time.time() - start_time
            print(f"⏱️ OCR completed in {processing_time:.2f}s, got {len(text)} chars")
            
            if text:
                print(f"📝 First 200 chars: {text[:200]}")
            
            return text
            
        except pytesseract.TesseractError as e:
            print(f"❌ Tesseract error: {e}")
            
            # Try a fallback approach with image-to-data
            try:
                print("🔄 Trying fallback OCR approach...")
                if 'gray' in locals():
                    # Try getting bounding boxes instead
                    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT, timeout=10)
                    text = ' '.join([word for word in data['text'] if word.strip()])
                    print(f"📝 Fallback got {len(text)} chars")
                    return text
            except:
                pass
            
            return ""
            
        except Exception as e:
            print(f"❌ Error extracting text from image: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return ""
            
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
    
    def extract_transaction_details(self, text):
        """Intelligently extract amount and reference - only from CashOut transactions"""
        try:
            start_time = time.time()
            
            # Clean text but preserve structure
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line:  # Keep non-empty lines
                    cleaned_lines.append(line)
            
            cleaned_text = '\n'.join(cleaned_lines)
            
            print(f"🔍 Processing text ({len(cleaned_text)} chars)")
            if cleaned_text:
                print(f"📄 Sample:\n{cleaned_text[:300]}")
            
            # Find all CashOut transactions in the text
            cashout_transactions = self._find_cashout_transactions(cleaned_text)
            
            if not cashout_transactions:
                print("❌ No CashOut transactions found in text")
                # Try alternative approach: look for any transaction-like text
                print("🔄 Trying alternative transaction detection...")
                cashout_transactions = self._find_any_transactions(cleaned_text)
            
            if not cashout_transactions:
                return {'reference': None, 'amount': None, 'confidence': 0.0, 'raw_text': cleaned_text}
            
            print(f"✅ Found {len(cashout_transactions)} potential transaction(s)")
            
            # Take the LAST transaction (most recent one) that has most data
            best_transaction = None
            best_score = -1
            
            for i, transaction in enumerate(cashout_transactions):
                has_ref = bool(self._extract_reference_from_transaction(transaction))
                has_amt = bool(self._extract_amount_from_transaction(transaction))
                score = (2 if has_ref else 0) + (1 if has_amt else 0)
                
                print(f"  Transaction {i+1}: score={score}, ref={has_ref}, amt={has_amt}")
                
                if score > best_score:
                    best_score = score
                    best_transaction = transaction
            
            if best_transaction:
                last_transaction = best_transaction
                print(f"📊 Using best transaction (score={best_score}): {last_transaction[:150]}...")
            else:
                last_transaction = cashout_transactions[-1]
                print(f"📊 Using last transaction: {last_transaction[:150]}...")
            
            # Extract details from the selected transaction
            details = {
                'reference': self._extract_reference_from_transaction(last_transaction),
                'amount': self._extract_amount_from_transaction(last_transaction),
                'confidence': 0.0,
                'raw_text': cleaned_text,
                'transaction_count': len(cashout_transactions),
                'transaction_used': last_transaction[:200] if last_transaction else None
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
                print(f"✅ Found amount: ${details['amount']:.2f}")
            else:
                print("❌ No amount found in selected transaction")
            
            details['confidence'] = found / 2.0
            
            processing_time = time.time() - start_time
            print(f"⏱️ Text processing completed in {processing_time:.2f}s")
            
            return details
            
        except Exception as e:
            print(f"❌ Error extracting details: {e}")
            import traceback
            traceback.print_exc()
            return {'reference': None, 'amount': None, 'confidence': 0.0, 'raw_text': text}
    
    def _find_cashout_transactions(self, text):
        """Find all CashOut transactions in the text with optimized regex"""
        transactions = []
        
        # First, try to find by line patterns (simpler)
        lines = text.split('\n')
        current_transaction = []
        in_transaction = False
        
        for line in lines:
            line_lower = line.lower()
            
            # Check if this line starts a transaction
            if any(keyword in line_lower for keyword in ['cashout', 'ecocash', 'transaction', 'txn']):
                if current_transaction and in_transaction:
                    # Save previous transaction
                    transaction_text = '\n'.join(current_transaction)
                    if len(transaction_text) > 20:  # Minimum meaningful length
                        transactions.append(transaction_text)
                    current_transaction = []
                
                in_transaction = True
                current_transaction.append(line)
            elif in_transaction:
                # Check if line continues transaction
                if any(keyword in line_lower for keyword in ['usd', 'id:', 'reference', 'amount', 'successful']):
                    current_transaction.append(line)
                elif line.strip() and len(current_transaction) > 0:
                    # If we have content and we're in a transaction, add it
                    current_transaction.append(line)
                else:
                    # End of transaction
                    if current_transaction:
                        transaction_text = '\n'.join(current_transaction)
                        if len(transaction_text) > 20:
                            transactions.append(transaction_text)
                    current_transaction = []
                    in_transaction = False
        
        # Add last transaction if exists
        if current_transaction and in_transaction:
            transaction_text = '\n'.join(current_transaction)
            if len(transaction_text) > 20:
                transactions.append(transaction_text)
        
        if transactions:
            print(f"✅ Found {len(transactions)} transaction(s) using line-based detection")
            return transactions
        
        # Fallback to regex patterns if line-based fails
        print("🔍 Line-based detection failed, trying regex patterns...")
        
        # Optimized patterns
        cashout_patterns = [
            # Pattern for structured confirmation
            r'(CashOut[^\n]{0,100}?(?:USD|ZWL|\$)[^\n]{0,200}?(?:Txn\s*ID|ID:)[^\n]{0,100}?[A-Z0-9]{2,}\.[A-Z0-9]{4,}\.[A-Z0-9]{4,})',
            
            # Simpler pattern
            r'(CashOut[^\n]{0,150}?\d+\.?\d*[^\n]{0,150})',
        ]
        
        for i, pattern in enumerate(cashout_patterns):
            try:
                matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
                if matches:
                    transactions.extend(matches)
                    print(f"🔍 Regex pattern {i+1} found {len(matches)} transaction(s)")
            except re.error as e:
                print(f"⚠️ Regex pattern {i+1} error: {e}")
                continue
        
        return transactions
    
    def _find_any_transactions(self, text):
        """Find any transaction-like text when CashOut not found"""
        transactions = []
        lines = text.split('\n')
        
        # Look for patterns that might indicate a transaction
        for i in range(len(lines)):
            line = lines[i]
            line_lower = line.lower()
            
            # Check for amount patterns
            amount_patterns = [
                r'USD\s*\d+\.?\d*',
                r'\$\s*\d+\.?\d*',
                r'\d+\.\d{2}\s*(?:USD|\$)',
            ]
            
            has_amount = any(re.search(pattern, line_lower) for pattern in amount_patterns)
            has_reference = bool(re.search(r'[A-Z0-9]{2,}\.[A-Z0-9]{4,}\.[A-Z0-9]{4,}', line))
            
            if has_amount or has_reference:
                # Get context around this line
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                transaction = '\n'.join(lines[start:end])
                transactions.append(transaction)
                print(f"🔍 Found potential transaction at line {i+1}")
        
        return transactions
    
    def _extract_reference_from_transaction(self, transaction_text):
        """Extract reference from a single transaction block"""
        if not transaction_text:
            return None
            
        # First, try to find in the text directly
        patterns = [
            r'([A-Z0-9]{2,}\.[A-Z0-9]{4,}\.[A-Z0-9]{4,})',  # Standard EcoCash format
            r'(?:Txn\s*ID|ID:)\s*([A-Z0-9\.]+)',  # With label
            r'([A-Z]{2}\d{6}\.\d{4}\.[A-Z]\d{5})',  # Specific format
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, transaction_text, re.IGNORECASE)
            if matches:
                for ref in matches:
                    ref = re.sub(r'\s+', '', ref)
                    # Validate reference format
                    if len(ref) >= 10 and ref.count('.') >= 2:
                        print(f"🔍 Found reference with pattern: {ref}")
                        return ref
        
        return None
    
    def _extract_amount_from_transaction(self, transaction_text):
        """Extract amount from a single transaction block"""
        if not transaction_text:
            return None
            
        patterns = [
            r'USD\s*(\d+\.\d{2})',  # USD 10.00
            r'USD\s*(\d+)',         # USD 10
            r'\$\s*(\d+\.\d{2})',   # $10.00
            r'\$\s*(\d+)',          # $10
            r'(\d+\.\d{2})\s*USD',  # 10.00 USD
            r'Amount[^\d]*(\d+\.\d{2})',  # Amount: 10.00
            r'CashOut[^\d]*(\d+\.\d{2})', # CashOut 10.00
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, transaction_text, re.IGNORECASE)
            if matches:
                try:
                    amount = float(matches[0])
                    # Validate reasonable amount range
                    if 0.1 <= amount <= 10000:
                        return round(amount, 2)
                except (ValueError, TypeError) as e:
                    print(f"⚠️ Could not parse amount '{matches[0]}': {e}")
                    continue
        
        return None
    
    def process_pop_image(self, image_file):
        """Intelligent processing - extract only from CashOut transactions"""
        total_start = time.time()
        
        try:
            print(f"🖼️ Starting intelligent OCR processing at {time.strftime('%H:%M:%S')}...")
            
            # Step 1: Extract text
            text_start = time.time()
            text = self.extract_text_from_image(image_file)
            text_time = time.time() - text_start
            print(f"⏱️ Text extraction completed in {text_time:.2f}s")
            
            if not text or len(text.strip()) < 5:
                print("❌ No meaningful text extracted")
                # Try one more time with different preprocessing
                print("🔄 Retrying with alternative preprocessing...")
                
                # Reset file pointer if possible
                if hasattr(image_file, 'seek'):
                    image_file.seek(0)
                    
                text_start = time.time()
                text = self._extract_text_alternative(image_file)
                retry_time = time.time() - text_start
                print(f"⏱️ Retry completed in {retry_time:.2f}s")
                
                if not text or len(text.strip()) < 5:
                    return {
                        'success': False,
                        'error': 'No meaningful text could be extracted from image',
                        'is_valid': False,
                        'validation_message': 'No readable text found in image',
                        'processing_time': time.time() - total_start
                    }
            
            print(f"📝 Text extracted successfully ({len(text)} chars)")
            
            # Step 2: Extract details
            details_start = time.time()
            details = self.extract_transaction_details(text)
            details_time = time.time() - details_start
            print(f"⏱️ Details extraction completed in {details_time:.2f}s")
            
            is_valid = details['reference'] is not None and details['amount'] is not None
            
            # Build informative message
            if details.get('transaction_count', 0) > 0:
                if is_valid:
                    validation_msg = f"✅ Valid - Found {details['transaction_count']} transaction(s) with complete data"
                else:
                    missing = []
                    if not details['reference']:
                        missing.append('reference')
                    if not details['amount']:
                        missing.append('amount')
                    validation_msg = f"⚠️ Partial - Found {details['transaction_count']} transaction(s) but missing: {', '.join(missing)}"
            else:
                validation_msg = "❌ No transactions found in text"
            
            total_time = time.time() - total_start
            print(f"✅ Total processing completed in {total_time:.2f}s")
            
            return {
                'success': True,
                'is_valid': is_valid,
                'extracted_text': text[:500] + "..." if len(text) > 500 else text,
                'transaction_details': details,
                'validation_message': validation_msg,
                'processing_time': total_time,
                'ocr_time': text_time,
                'processing_time_breakdown': {
                    'ocr': text_time,
                    'text_processing': details_time,
                    'total': total_time
                }
            }
            
        except TimeoutException as e:
            total_time = time.time() - total_start
            print(f"⏰ Timeout after {total_time:.2f}s: {e}")
            return {
                'success': False,
                'error': str(e),
                'is_valid': False,
                'validation_message': f'Processing timeout after {total_time:.1f}s',
                'processing_time': total_time
            }
        except Exception as e:
            total_time = time.time() - total_start
            print(f"❌ Unexpected error after {total_time:.2f}s: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': f'{type(e).__name__}: {str(e)}',
                'is_valid': False,
                'validation_message': f'Processing error: {str(e)[:100]}',
                'processing_time': total_time
            }
    
    def _extract_text_alternative(self, image_file):
        """Alternative text extraction method"""
        try:
            # Simple approach: just read image and do minimal processing
            if hasattr(image_file, 'read'):
                image = Image.open(io.BytesIO(image_file.read()))
            else:
                image = Image.open(image_file)
            
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Simple threshold
            image_np = np.array(image)
            _, thresholded = cv2.threshold(image_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Use simple OCR config
            text = pytesseract.image_to_string(
                thresholded, 
                config='--oem 1 --psm 6',
                timeout=10
            )
            
            return text
            
        except Exception as e:
            print(f"❌ Alternative extraction failed: {e}")
            return ""
    
    def safe_process_image(self, image_file):
        """Process image with timeout protection using signal"""
        # Save original signal handler
        original_handler = signal.signal(signal.SIGALRM, self._timeout_handler)
        signal.alarm(self.timeout_seconds)
        
        try:
            result = self.process_pop_image(image_file)
            signal.alarm(0)  # Disable the alarm
            return result
        except TimeoutException as e:
            return {
                'success': False,
                'error': str(e),
                'is_valid': False,
                'validation_message': f'Processing timeout after {self.timeout_seconds} seconds'
            }
        finally:
            # Restore original signal handler
            signal.alarm(0)
            signal.signal(signal.SIGALRM, original_handler)
    
    def quick_process(self, image_file):
        """Quick processing with minimal steps"""
        try:
            print("⚡ Quick processing mode...")
            start_time = time.time()
            
            # Simple image loading
            if hasattr(image_file, 'read'):
                image = Image.open(io.BytesIO(image_file.read()))
            else:
                image = Image.open(image_file)
            
            # Resize to reasonable size
            image.thumbnail((800, 1200), Image.Resampling.LANCZOS)
            
            # Convert to grayscale
            image = image.convert('L')
            
            # Simple OCR
            text = pytesseract.image_to_string(
                np.array(image),
                config='--oem 1 --psm 6',
                timeout=10
            )
            
            # Quick extraction
            details = self.extract_transaction_details(text)
            
            return {
                'success': True,
                'is_valid': details['reference'] is not None and details['amount'] is not None,
                'extracted_text': text[:300],
                'transaction_details': details,
                'processing_time': time.time() - start_time
            }
            
        except Exception as e:
            print(f"❌ Quick processing failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }