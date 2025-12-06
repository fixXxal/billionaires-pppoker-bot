"""
Django Management Command: Clean Up Test Data
Usage: python manage.py cleanup_test_data

WARNING: This command DELETES ALL test data from the database!
- Deletes all users (except admins)
- Deletes all transactions (deposits, withdrawals, spins)
- Deletes all requests (join, seat, cashback)
- Deletes all support messages
- Deletes all 50/50 investments
- Keeps: Admins, Exchange Rates, Counter Status, Promo Codes

This prepares your database for production/live users.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import (
    User, Deposit, Withdrawal, SpinUser, SpinAward, SpinUsage, SpinHistory,
    JoinRequest, SeatRequest, CashbackRequest, SupportMessage,
    FiftyFiftyInvestment, UserCredit, InventoryTransaction, ClubBalance,
    Admin
)


class Command(BaseCommand):
    help = 'Clean up all test data from database (keeps admins and system settings)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Actually perform the cleanup (without this flag, it only shows what would be deleted)',
        )

    def handle(self, *args, **options):
        confirm = options['confirm']

        self.stdout.write(self.style.WARNING('\n' + '='*60))
        self.stdout.write(self.style.WARNING('DATABASE CLEANUP - TEST DATA REMOVAL'))
        self.stdout.write(self.style.WARNING('='*60 + '\n'))

        # Count what will be deleted
        admin_count = Admin.objects.count()
        user_count = User.objects.count()
        deposit_count = Deposit.objects.count()
        withdrawal_count = Withdrawal.objects.count()
        spin_user_count = SpinUser.objects.count()
        spin_history_count = SpinHistory.objects.count()
        spin_usage_count = SpinUsage.objects.count()
        join_request_count = JoinRequest.objects.count()
        seat_request_count = SeatRequest.objects.count()
        cashback_request_count = CashbackRequest.objects.count()
        support_message_count = SupportMessage.objects.count()
        fiftyfifty_count = FiftyFiftyInvestment.objects.count()
        user_credit_count = UserCredit.objects.count()
        inventory_count = InventoryTransaction.objects.count()
        club_balance_count = ClubBalance.objects.count()

        self.stdout.write(self.style.NOTICE('Current Database Contents:'))
        self.stdout.write(f'  👥 Admins: {admin_count} (WILL BE KEPT)')
        self.stdout.write(f'  👤 Users: {user_count}')
        self.stdout.write(f'  💰 Deposits: {deposit_count}')
        self.stdout.write(f'  💸 Withdrawals: {withdrawal_count}')
        self.stdout.write(f'  🎰 Spin Users: {spin_user_count}')
        self.stdout.write(f'  🎲 Spin History: {spin_history_count}')
        self.stdout.write(f'  📊 Spin Usage: {spin_usage_count}')
        self.stdout.write(f'  🚪 Join Requests: {join_request_count}')
        self.stdout.write(f'  💺 Seat Requests: {seat_request_count}')
        self.stdout.write(f'  🎁 Cashback Requests: {cashback_request_count}')
        self.stdout.write(f'  💬 Support Messages: {support_message_count}')
        self.stdout.write(f'  💎 50/50 Investments: {fiftyfifty_count}')
        self.stdout.write(f'  💳 User Credits: {user_credit_count}')
        self.stdout.write(f'  📦 Inventory Transactions: {inventory_count}')
        self.stdout.write(f'  🏦 Club Balances: {club_balance_count}')

        total_to_delete = (
            user_count + deposit_count + withdrawal_count +
            spin_user_count + spin_history_count + spin_usage_count +
            join_request_count + seat_request_count + cashback_request_count +
            support_message_count + fiftyfifty_count + user_credit_count +
            inventory_count + club_balance_count
        )

        self.stdout.write(f'\n  🗑️  TOTAL RECORDS TO DELETE: {total_to_delete}')

        if not confirm:
            self.stdout.write(self.style.WARNING('\n' + '='*60))
            self.stdout.write(self.style.WARNING('DRY RUN MODE - Nothing was deleted'))
            self.stdout.write(self.style.WARNING('='*60))
            self.stdout.write(self.style.NOTICE('\nTo actually perform the cleanup, run:'))
            self.stdout.write(self.style.SUCCESS('  python manage.py cleanup_test_data --confirm\n'))
            return

        # Final confirmation
        self.stdout.write(self.style.ERROR('\n⚠️  WARNING: This will PERMANENTLY DELETE all test data!'))
        self.stdout.write(self.style.NOTICE(f'⚠️  {total_to_delete} records will be deleted'))
        self.stdout.write(self.style.NOTICE('⚠️  This action CANNOT be undone!\n'))

        confirm_input = input('Type "DELETE ALL TEST DATA" to confirm: ')

        if confirm_input != "DELETE ALL TEST DATA":
            self.stdout.write(self.style.ERROR('\n❌ Cleanup cancelled - confirmation text did not match\n'))
            return

        self.stdout.write(self.style.WARNING('\n🗑️  Starting cleanup...'))

        try:
            with transaction.atomic():
                # Delete in correct order (respecting foreign key constraints)

                self.stdout.write('  Deleting Support Messages...')
                deleted_support = SupportMessage.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_support} support messages'))

                self.stdout.write('  Deleting 50/50 Investments...')
                deleted_fiftyfifty = FiftyFiftyInvestment.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_fiftyfifty} investments'))

                self.stdout.write('  Deleting Join Requests...')
                deleted_join = JoinRequest.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_join} join requests'))

                self.stdout.write('  Deleting Seat Requests...')
                deleted_seat = SeatRequest.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_seat} seat requests'))

                self.stdout.write('  Deleting Cashback Requests...')
                deleted_cashback = CashbackRequest.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_cashback} cashback requests'))

                self.stdout.write('  Deleting Spin History...')
                deleted_spin_history = SpinHistory.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_spin_history} spin history records'))

                self.stdout.write('  Deleting Spin Usage...')
                deleted_spin_usage = SpinUsage.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_spin_usage} spin usage records'))

                self.stdout.write('  Deleting Spin Users...')
                deleted_spin_users = SpinUser.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_spin_users} spin users'))

                self.stdout.write('  Deleting User Credits...')
                deleted_credits = UserCredit.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_credits} user credits'))

                self.stdout.write('  Deleting Inventory Transactions...')
                deleted_inventory = InventoryTransaction.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_inventory} inventory transactions'))

                self.stdout.write('  Deleting Club Balances...')
                deleted_club = ClubBalance.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_club} club balances'))

                self.stdout.write('  Deleting Deposits...')
                deleted_deposits = Deposit.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_deposits} deposits'))

                self.stdout.write('  Deleting Withdrawals...')
                deleted_withdrawals = Withdrawal.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_withdrawals} withdrawals'))

                self.stdout.write('  Deleting Users...')
                deleted_users = User.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'    ✅ Deleted {deleted_users} users'))

                # Calculate total
                total_deleted = (
                    deleted_support + deleted_fiftyfifty + deleted_join + deleted_seat +
                    deleted_cashback + deleted_spin_history + deleted_spin_usage +
                    deleted_spin_users + deleted_credits + deleted_inventory +
                    deleted_club + deleted_deposits + deleted_withdrawals + deleted_users
                )

                self.stdout.write(self.style.SUCCESS(f'\n✅ CLEANUP COMPLETE!'))
                self.stdout.write(self.style.SUCCESS(f'✅ Total records deleted: {total_deleted}'))

                # Show what was kept
                remaining_admins = Admin.objects.count()
                self.stdout.write(self.style.NOTICE(f'\n✅ Kept: {remaining_admins} admin accounts'))
                self.stdout.write(self.style.NOTICE('✅ Kept: All system settings (exchange rates, promo codes, etc.)'))

                self.stdout.write(self.style.SUCCESS('\n🎉 Database is now clean and ready for production users!\n'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error during cleanup: {e}'))
            self.stdout.write(self.style.ERROR('❌ Transaction rolled back - no changes were made\n'))
            raise
