import os
from django.core.management.base import BaseCommand
from django.core.files.uploadedfile import SimpleUploadedFile
from whatsapp.ocr_service import EcoCashOCRService

class Command(BaseCommand):
    help = 'Test OCR extraction from an image file'
    
    def add_arguments(self, parser):
        parser.add_argument('image_path', type=str, help='Path to the image file to test')
    
    def handle(self, *args, **options):
        image_path = options['image_path']
        
        if not os.path.exists(image_path):
            self.stdout.write(
                self.style.ERROR(f'❌ Image file not found: {image_path}')
            )
            return
        
        self.stdout.write(f'🧪 Testing OCR with image: {image_path}')
        
        ocr_service = EcoCashOCRService()
        result = ocr_service.process_pop_image(image_path)
        
        self.stdout.write('\n📊 OCR Results:')
        self.stdout.write(f'✅ Success: {result.get("success", False)}')
        self.stdout.write(f'✅ Valid: {result.get("is_valid", False)}')
        self.stdout.write(f'📝 Validation Message: {result.get("validation_message", "")}')
        
        if result.get('success'):
            details = result.get('transaction_details', {})
            self.stdout.write(f'💰 Extracted Amount: ${details.get("amount", "Not found")}')
            self.stdout.write(f'🔢 Extracted Reference: {details.get("reference", "Not found")}')
            self.stdout.write(f'🎯 Confidence: {details.get("confidence", 0):.1%}')
            
            self.stdout.write('\n📝 Extracted Text:')
            self.stdout.write(result.get('extracted_text', 'No text extracted'))
            
            if result.get('is_valid'):
                self.stdout.write(
                    self.style.SUCCESS('🎉 SUCCESS: Both amount and reference extracted!')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('⚠️  PARTIAL: Some fields missing')
                )
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ ERROR: {result.get("error", "Unknown error")}')
            )