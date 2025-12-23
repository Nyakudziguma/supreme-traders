from django.core.management.base import BaseCommand
from django.db import transaction
from finance.models import EcoCashTransaction  # Replace with your actual app name

class Command(BaseCommand):
    help = 'Set all withdrawal transactions to have 0 charges'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually making changes',
        )
        parser.add_argument(
            '--transaction-id',
            type=int,
            help='Fix only a specific transaction ID',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Fix transactions for a specific user only',
        )
        parser.add_argument(
            '--status',
            type=str,
            help='Fix transactions with specific status only (e.g., pending, completed)',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        transaction_id = options['transaction_id']
        user_id = options['user_id']
        status = options['status']
        
        # Build the queryset
        queryset = EcoCashTransaction.objects.filter(transaction_type='withdrawal')
        
        # Apply filters if provided
        if transaction_id:
            queryset = queryset.filter(id=transaction_id)
            self.stdout.write(f"Filtering by transaction ID: {transaction_id}")
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
            self.stdout.write(f"Filtering by user ID: {user_id}")
        
        if status:
            queryset = queryset.filter(status=status)
            self.stdout.write(f"Filtering by status: {status}")
        
        # Filter transactions that don't have 0 charge
        problem_transactions = queryset.exclude(charge=0)
        total_count = problem_transactions.count()
        
        self.stdout.write(self.style.WARNING(f"Found {total_count} withdrawal transactions with non-zero charges"))
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("No withdrawal transactions need fixing!"))
            return
        
        # Show summary of charges
        self.stdout.write("\n" + "="*50)
        self.stdout.write("CHARGE SUMMARY:")
        
        # Group by charge value to show distribution
        from django.db.models import Count, Sum, Avg, Max, Min
        charge_stats = problem_transactions.values('charge').annotate(
            count=Count('id'),
            total_amount=Sum('amount'),
            avg_amount=Avg('amount'),
            max_amount=Max('amount'),
            min_amount=Min('amount')
        ).order_by('-charge')
        
        for stat in charge_stats:
            charge = stat['charge']
            count = stat['count']
            total = stat['total_amount']
            avg = stat['avg_amount']
            
            self.stdout.write(f"  Charge ${charge:.2f}: {count} transactions")
            self.stdout.write(f"    Total amount affected: ${total:.2f}")
            self.stdout.write(f"    Average transaction: ${avg:.2f}")
        
        self.stdout.write("="*50)
        
        # Show first 10 transactions for preview
        if not transaction_id and total_count > 0:
            preview_count = min(10, total_count)
            preview = problem_transactions[:preview_count]
            
            self.stdout.write(f"\nPREVIEW (first {preview_count} of {total_count}):")
            self.stdout.write("-" * 80)
            self.stdout.write(f"{'ID':<8} {'User':<15} {'Amount':<12} {'Charge':<10} {'Status':<12} {'Created'}")
            self.stdout.write("-" * 80)
            
            for tx in preview:
                self.stdout.write(
                    f"{tx.id:<8} {str(tx.user)[:14]:<15} "
                    f"${tx.amount:<11.2f} ${tx.charge:<9.2f} "
                    f"{tx.status:<12} {tx.created_at.strftime('%Y-%m-%d')}"
                )
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\nDRY RUN: Would set charges to 0 for {total_count} withdrawal transactions"
            ))
            if total_count > 0:
                total_amount_saved = sum(tx.charge for tx in problem_transactions)
                self.stdout.write(self.style.WARNING(
                    f"Total charges that would be removed: ${total_amount_saved:.2f}"
                ))
            return
        
        # Ask for confirmation
        if total_count > 10:  # Only ask for confirmation if more than 10 transactions
            confirm = input(f"\nAre you sure you want to set charges to 0 for {total_count} transactions? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return
        
        # Actually update the transactions
        self.stdout.write("\nUpdating transactions...")
        
        updated_count = 0
        with transaction.atomic():
            for tx in problem_transactions.iterator(chunk_size=100):
                old_charge = tx.charge
                tx.charge = 0
                tx.save(update_fields=['charge'])
                updated_count += 1
                
                if updated_count % 100 == 0:
                    self.stdout.write(f"Updated {updated_count}/{total_count} transactions...")
        
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Successfully updated {updated_count} withdrawal transactions to have 0 charges!"
        ))
        
        if updated_count > 0:
            # Show some statistics about the fix
            self.stdout.write("\n" + "="*50)
            self.stdout.write("UPDATE SUMMARY:")
            
            # Calculate some stats
            total_charges_removed = sum(tx.charge for tx in problem_transactions)
            
            self.stdout.write(f"Total transactions fixed: {updated_count}")
            self.stdout.write(f"Total charges removed: ${total_charges_removed:.2f}")
            
            # Show distribution by status
            from django.db.models import Count
            status_dist = problem_transactions.values('status').annotate(
                count=Count('id'),
                total_charges=Sum('charge')
            )
            
            if status_dist:
                self.stdout.write("\nFixed by status:")
                for stat in status_dist:
                    self.stdout.write(f"  {stat['status']}: {stat['count']} transactions (${stat['total_charges']:.2f} total)")
            
            self.stdout.write("="*50)