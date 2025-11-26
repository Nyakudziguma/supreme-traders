from django.core.management.base import BaseCommand
from finance.models import TransactionCharge

class Command(BaseCommand):
    help = 'Set up the default transaction charges'
    
    def handle(self, *args, **options):
        charges_data = [
            # Fixed fee ranges
            {'min_amount': 1.00, 'max_amount': 2.99, 'fixed_charge': 0.75, 'is_percentage': False},
            {'min_amount': 3.00, 'max_amount': 3.59, 'fixed_charge': 0.85, 'is_percentage': False},
            {'min_amount': 3.60, 'max_amount': 4.99, 'fixed_charge': 1.30, 'is_percentage': False},
            {'min_amount': 5.00, 'max_amount': 5.99, 'fixed_charge': 1.35, 'is_percentage': False},
            {'min_amount': 6.00, 'max_amount': 6.99, 'fixed_charge': 1.40, 'is_percentage': False},
            {'min_amount': 7.00, 'max_amount': 7.99, 'fixed_charge': 1.45, 'is_percentage': False},
            {'min_amount': 8.00, 'max_amount': 8.99, 'fixed_charge': 1.75, 'is_percentage': False},
            {'min_amount': 9.00, 'max_amount': 9.99, 'fixed_charge': 1.85, 'is_percentage': False},
            # Percentage range for $10+
            {'min_amount': 10.00, 'max_amount': 10000.00, 'fixed_charge': 0.00, 'is_percentage': True, 'percentage_rate': 10.00, 'additional_fee': 0.90},
        ]
        
        for charge_data in charges_data:
            TransactionCharge.objects.get_or_create(
                min_amount=charge_data['min_amount'],
                defaults=charge_data
            )
        
        self.stdout.write(
            self.style.SUCCESS('Successfully set up transaction charges')
        )