"""
Background Sync Script: Django to Google Sheets
Synchronizes all unsynced records from Django database to Google Sheets
Run this periodically (e.g., every 30 seconds) to keep Sheets updated
"""

import os
import sys
import django
from datetime import datetime

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'billionaires_backend.settings')
django.setup()

# Import after Django setup
from api.models import (
    User, Deposit, Withdrawal, SpinUser, SpinHistory,
    JoinRequest, SeatRequest, CashbackRequest, PaymentAccount,
    Admin, CounterStatus, PromoCode, SupportMessage,
    UserCredit, ExchangeRate, FiftyFiftyInvestment,
    ClubBalance, InventoryTransaction
)
from sheets_manager import SheetsManager


class DjangoToSheetsSync:
    """Handles synchronization from Django to Google Sheets"""

    def __init__(self):
        self.sheets = SheetsManager()
        self.sync_stats = {
            'total_synced': 0,
            'errors': []
        }

    def sync_users(self):
        """Sync User records to Users sheet"""
        unsynced = User.objects.filter(synced_to_sheets=False)

        for user in unsynced:
            try:
                row = [
                    user.telegram_id,
                    user.username,
                    user.pppoker_id,
                    float(user.balance),
                    float(user.club_balance),
                    user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    user.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                ]

                # Find existing row or append new
                existing_rows = self.sheets.get_all_records('Users')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):  # Start at 2 (skip header)
                    if str(existing.get('Telegram ID')) == str(user.telegram_id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    # Update existing row
                    self.sheets.worksheet('Users').update(f'A{existing_row_idx}:G{existing_row_idx}', [row])
                else:
                    # Append new row
                    self.sheets.worksheet('Users').append_row(row)

                # Mark as synced
                user.synced_to_sheets = True
                user.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"User {user.id}: {str(e)}")

    def sync_deposits(self):
        """Sync Deposit records to Deposits sheet"""
        unsynced = Deposit.objects.filter(synced_to_sheets=False).select_related('user')

        for deposit in unsynced:
            try:
                row = [
                    deposit.id,
                    deposit.user.telegram_id,
                    deposit.user.username,
                    float(deposit.amount),
                    deposit.method,
                    deposit.account_name,
                    deposit.proof_image_path,
                    deposit.pppoker_id,
                    deposit.status,
                    deposit.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    deposit.approved_at.strftime('%Y-%m-%d %H:%M:%S') if deposit.approved_at else '',
                    str(deposit.approved_by) if deposit.approved_by else '',
                    deposit.rejection_reason
                ]

                # Find existing row or append
                existing_rows = self.sheets.get_all_records('Deposits')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(deposit.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Deposits').update(f'A{existing_row_idx}:M{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Deposits').append_row(row)

                deposit.synced_to_sheets = True
                deposit.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"Deposit {deposit.id}: {str(e)}")

    def sync_withdrawals(self):
        """Sync Withdrawal records to Withdrawals sheet"""
        unsynced = Withdrawal.objects.filter(synced_to_sheets=False).select_related('user')

        for withdrawal in unsynced:
            try:
                row = [
                    withdrawal.id,
                    withdrawal.user.telegram_id,
                    withdrawal.user.username,
                    float(withdrawal.amount),
                    withdrawal.method,
                    withdrawal.account_name,
                    withdrawal.account_number,
                    withdrawal.pppoker_id,
                    withdrawal.status,
                    withdrawal.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    withdrawal.approved_at.strftime('%Y-%m-%d %H:%M:%S') if withdrawal.approved_at else '',
                    str(withdrawal.approved_by) if withdrawal.approved_by else '',
                    withdrawal.rejection_reason
                ]

                existing_rows = self.sheets.get_all_records('Withdrawals')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(withdrawal.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Withdrawals').update(f'A{existing_row_idx}:M{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Withdrawals').append_row(row)

                withdrawal.synced_to_sheets = True
                withdrawal.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"Withdrawal {withdrawal.id}: {str(e)}")

    def sync_spin_users(self):
        """Sync SpinUser records to Spin_Users sheet"""
        unsynced = SpinUser.objects.filter(synced_to_sheets=False).select_related('user')

        for spin_user in unsynced:
            try:
                row = [
                    spin_user.user.telegram_id,
                    spin_user.user.username,
                    spin_user.available_spins,
                    spin_user.total_spins_used,
                    spin_user.total_chips_earned,
                    spin_user.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                ]

                existing_rows = self.sheets.get_all_records('Spin_Users')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('Telegram ID')) == str(spin_user.user.telegram_id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Spin_Users').update(f'A{existing_row_idx}:F{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Spin_Users').append_row(row)

                spin_user.synced_to_sheets = True
                spin_user.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"SpinUser {spin_user.id}: {str(e)}")

    def sync_spin_history(self):
        """Sync SpinHistory records to Spin_History sheet"""
        unsynced = SpinHistory.objects.filter(synced_to_sheets=False).select_related('user')

        for spin in unsynced:
            try:
                row = [
                    spin.id,
                    spin.user.telegram_id,
                    spin.user.username,
                    spin.prize,
                    spin.chips,
                    spin.pppoker_id,
                    spin.status,
                    spin.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    spin.approved_at.strftime('%Y-%m-%d %H:%M:%S') if spin.approved_at else '',
                    str(spin.approved_by) if spin.approved_by else ''
                ]

                existing_rows = self.sheets.get_all_records('Spin_History')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(spin.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Spin_History').update(f'A{existing_row_idx}:J{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Spin_History').append_row(row)

                spin.synced_to_sheets = True
                spin.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"SpinHistory {spin.id}: {str(e)}")

    def sync_join_requests(self):
        """Sync JoinRequest records to Join_Requests sheet"""
        unsynced = JoinRequest.objects.filter(synced_to_sheets=False).select_related('user')

        for join_req in unsynced:
            try:
                row = [
                    join_req.id,
                    join_req.user.telegram_id,
                    join_req.user.username,
                    join_req.pppoker_id,
                    join_req.status,
                    join_req.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    join_req.approved_at.strftime('%Y-%m-%d %H:%M:%S') if join_req.approved_at else '',
                    str(join_req.approved_by) if join_req.approved_by else '',
                    join_req.rejection_reason
                ]

                existing_rows = self.sheets.get_all_records('Join_Requests')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(join_req.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Join_Requests').update(f'A{existing_row_idx}:I{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Join_Requests').append_row(row)

                join_req.synced_to_sheets = True
                join_req.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"JoinRequest {join_req.id}: {str(e)}")

    def sync_seat_requests(self):
        """Sync SeatRequest records to Seat_Requests sheet"""
        unsynced = SeatRequest.objects.filter(synced_to_sheets=False).select_related('user')

        for seat_req in unsynced:
            try:
                row = [
                    seat_req.id,
                    seat_req.user.telegram_id,
                    seat_req.user.username,
                    float(seat_req.amount),
                    seat_req.slip_image_path,
                    seat_req.pppoker_id,
                    seat_req.status,
                    seat_req.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    seat_req.approved_at.strftime('%Y-%m-%d %H:%M:%S') if seat_req.approved_at else '',
                    str(seat_req.approved_by) if seat_req.approved_by else '',
                    seat_req.rejection_reason
                ]

                existing_rows = self.sheets.get_all_records('Seat_Requests')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(seat_req.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Seat_Requests').update(f'A{existing_row_idx}:K{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Seat_Requests').append_row(row)

                seat_req.synced_to_sheets = True
                seat_req.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"SeatRequest {seat_req.id}: {str(e)}")

    def sync_cashback_requests(self):
        """Sync CashbackRequest records to Cashback_Requests sheet"""
        unsynced = CashbackRequest.objects.filter(synced_to_sheets=False).select_related('user')

        for cashback in unsynced:
            try:
                row = [
                    cashback.id,
                    cashback.user.telegram_id,
                    cashback.user.username,
                    cashback.week_start.strftime('%Y-%m-%d'),
                    cashback.week_end.strftime('%Y-%m-%d'),
                    float(cashback.investment_amount),
                    float(cashback.cashback_amount),
                    float(cashback.cashback_percentage),
                    cashback.pppoker_id,
                    cashback.status,
                    cashback.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    cashback.approved_at.strftime('%Y-%m-%d %H:%M:%S') if cashback.approved_at else '',
                    str(cashback.approved_by) if cashback.approved_by else '',
                    cashback.rejection_reason
                ]

                existing_rows = self.sheets.get_all_records('Cashback_Requests')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(cashback.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Cashback_Requests').update(f'A{existing_row_idx}:N{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Cashback_Requests').append_row(row)

                cashback.synced_to_sheets = True
                cashback.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"CashbackRequest {cashback.id}: {str(e)}")

    def sync_payment_accounts(self):
        """Sync PaymentAccount records to Payment_Accounts sheet"""
        unsynced = PaymentAccount.objects.filter(synced_to_sheets=False)

        for account in unsynced:
            try:
                row = [
                    account.id,
                    account.method,
                    account.account_name,
                    account.account_number,
                    'Yes' if account.is_active else 'No',
                    account.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    account.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                ]

                existing_rows = self.sheets.get_all_records('Payment_Accounts')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(account.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Payment_Accounts').update(f'A{existing_row_idx}:G{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Payment_Accounts').append_row(row)

                account.synced_to_sheets = True
                account.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"PaymentAccount {account.id}: {str(e)}")

    def sync_admins(self):
        """Sync Admin records to Admins sheet"""
        unsynced = Admin.objects.filter(synced_to_sheets=False)

        for admin in unsynced:
            try:
                row = [
                    admin.telegram_id,
                    admin.username,
                    admin.role,
                    'Yes' if admin.is_active else 'No',
                    admin.created_at.strftime('%Y-%m-%d %H:%M:%S')
                ]

                existing_rows = self.sheets.get_all_records('Admins')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('Telegram ID')) == str(admin.telegram_id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Admins').update(f'A{existing_row_idx}:E{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Admins').append_row(row)

                admin.synced_to_sheets = True
                admin.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"Admin {admin.id}: {str(e)}")

    def sync_counter_status(self):
        """Sync CounterStatus to Counter_Status sheet"""
        try:
            counter = CounterStatus.load()

            if not counter.synced_to_sheets:
                row = [
                    'Open' if counter.is_open else 'Closed',
                    counter.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                    str(counter.updated_by)
                ]

                # Always update row 2 (single record)
                self.sheets.worksheet('Counter_Status').update('A2:C2', [row])

                counter.synced_to_sheets = True
                counter.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

        except Exception as e:
            self.sync_stats['errors'].append(f"CounterStatus: {str(e)}")

    def sync_promo_codes(self):
        """Sync PromoCode records to Promo_Codes sheet"""
        unsynced = PromoCode.objects.filter(synced_to_sheets=False)

        for promo in unsynced:
            try:
                row = [
                    promo.id,
                    promo.code,
                    float(promo.percentage),
                    promo.start_date.strftime('%Y-%m-%d'),
                    promo.end_date.strftime('%Y-%m-%d'),
                    'Yes' if promo.is_active else 'No',
                    promo.created_at.strftime('%Y-%m-%d %H:%M:%S')
                ]

                existing_rows = self.sheets.get_all_records('Promo_Codes')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(promo.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Promo_Codes').update(f'A{existing_row_idx}:G{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Promo_Codes').append_row(row)

                promo.synced_to_sheets = True
                promo.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"PromoCode {promo.id}: {str(e)}")

    def sync_support_messages(self):
        """Sync SupportMessage records to Support_Messages sheet"""
        unsynced = SupportMessage.objects.filter(synced_to_sheets=False).select_related('user')

        for msg in unsynced:
            try:
                row = [
                    msg.id,
                    msg.user.telegram_id,
                    msg.user.username,
                    msg.message,
                    'Yes' if msg.is_from_user else 'No',
                    str(msg.replied_by) if msg.replied_by else '',
                    msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
                ]

                existing_rows = self.sheets.get_all_records('Support_Messages')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(msg.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Support_Messages').update(f'A{existing_row_idx}:G{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Support_Messages').append_row(row)

                msg.synced_to_sheets = True
                msg.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"SupportMessage {msg.id}: {str(e)}")

    def sync_user_credits(self):
        """Sync UserCredit records to User_Credits sheet"""
        unsynced = UserCredit.objects.filter(synced_to_sheets=False).select_related('user')

        for credit in unsynced:
            try:
                row = [
                    credit.id,
                    credit.user.telegram_id,
                    credit.user.username,
                    float(credit.amount),
                    credit.credit_type,
                    credit.description,
                    credit.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    str(credit.created_by)
                ]

                existing_rows = self.sheets.get_all_records('User_Credits')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(credit.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('User_Credits').update(f'A{existing_row_idx}:H{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('User_Credits').append_row(row)

                credit.synced_to_sheets = True
                credit.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"UserCredit {credit.id}: {str(e)}")

    def sync_exchange_rates(self):
        """Sync ExchangeRate records to Exchange_Rates sheet"""
        unsynced = ExchangeRate.objects.filter(synced_to_sheets=False)

        for rate in unsynced:
            try:
                row = [
                    rate.id,
                    rate.currency_from,
                    rate.currency_to,
                    float(rate.rate),
                    'Yes' if rate.is_active else 'No',
                    rate.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    rate.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                ]

                existing_rows = self.sheets.get_all_records('Exchange_Rates')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(rate.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Exchange_Rates').update(f'A{existing_row_idx}:G{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Exchange_Rates').append_row(row)

                rate.synced_to_sheets = True
                rate.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"ExchangeRate {rate.id}: {str(e)}")

    def sync_investments(self):
        """Sync FiftyFiftyInvestment records to 50-50_Investments sheet"""
        unsynced = FiftyFiftyInvestment.objects.filter(synced_to_sheets=False).select_related('user')

        for investment in unsynced:
            try:
                row = [
                    investment.id,
                    investment.user.telegram_id,
                    investment.user.username,
                    float(investment.investment_amount),
                    float(investment.profit_share),
                    float(investment.loss_share),
                    investment.status,
                    investment.start_date.strftime('%Y-%m-%d'),
                    investment.end_date.strftime('%Y-%m-%d') if investment.end_date else '',
                    investment.notes,
                    investment.created_at.strftime('%Y-%m-%d %H:%M:%S')
                ]

                existing_rows = self.sheets.get_all_records('50-50_Investments')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(investment.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('50-50_Investments').update(f'A{existing_row_idx}:K{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('50-50_Investments').append_row(row)

                investment.synced_to_sheets = True
                investment.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"FiftyFiftyInvestment {investment.id}: {str(e)}")

    def sync_club_balances(self):
        """Sync ClubBalance records to Club_Balances sheet"""
        unsynced = ClubBalance.objects.filter(synced_to_sheets=False).select_related('user')

        for club_balance in unsynced:
            try:
                row = [
                    club_balance.id,
                    club_balance.user.telegram_id,
                    club_balance.user.username,
                    float(club_balance.balance),
                    club_balance.last_updated.strftime('%Y-%m-%d %H:%M:%S'),
                    club_balance.notes
                ]

                existing_rows = self.sheets.get_all_records('Club_Balances')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(club_balance.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Club_Balances').update(f'A{existing_row_idx}:F{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Club_Balances').append_row(row)

                club_balance.synced_to_sheets = True
                club_balance.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"ClubBalance {club_balance.id}: {str(e)}")

    def sync_inventory_transactions(self):
        """Sync InventoryTransaction records to Inventory_Transactions sheet"""
        unsynced = InventoryTransaction.objects.filter(synced_to_sheets=False)

        for transaction in unsynced:
            try:
                row = [
                    transaction.id,
                    transaction.item_name,
                    transaction.quantity,
                    transaction.transaction_type,
                    float(transaction.price_per_unit),
                    float(transaction.total_amount),
                    transaction.notes,
                    transaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    str(transaction.created_by)
                ]

                existing_rows = self.sheets.get_all_records('Inventory_Transactions')
                existing_row_idx = None

                for idx, existing in enumerate(existing_rows, start=2):
                    if str(existing.get('ID')) == str(transaction.id):
                        existing_row_idx = idx
                        break

                if existing_row_idx:
                    self.sheets.worksheet('Inventory_Transactions').update(f'A{existing_row_idx}:I{existing_row_idx}', [row])
                else:
                    self.sheets.worksheet('Inventory_Transactions').append_row(row)

                transaction.synced_to_sheets = True
                transaction.save(update_fields=['synced_to_sheets'])
                self.sync_stats['total_synced'] += 1

            except Exception as e:
                self.sync_stats['errors'].append(f"InventoryTransaction {transaction.id}: {str(e)}")

    def run_full_sync(self):
        """Run complete sync for all models"""
        print(f"\n{'='*60}")
        print(f"Django to Google Sheets Sync Started")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        sync_methods = [
            ('Users', self.sync_users),
            ('Deposits', self.sync_deposits),
            ('Withdrawals', self.sync_withdrawals),
            ('Spin Users', self.sync_spin_users),
            ('Spin History', self.sync_spin_history),
            ('Join Requests', self.sync_join_requests),
            ('Seat Requests', self.sync_seat_requests),
            ('Cashback Requests', self.sync_cashback_requests),
            ('Payment Accounts', self.sync_payment_accounts),
            ('Admins', self.sync_admins),
            ('Counter Status', self.sync_counter_status),
            ('Promo Codes', self.sync_promo_codes),
            ('Support Messages', self.sync_support_messages),
            ('User Credits', self.sync_user_credits),
            ('Exchange Rates', self.sync_exchange_rates),
            ('50-50 Investments', self.sync_investments),
            ('Club Balances', self.sync_club_balances),
            ('Inventory Transactions', self.sync_inventory_transactions),
        ]

        for name, method in sync_methods:
            print(f"Syncing {name}...", end=' ')
            before_count = self.sync_stats['total_synced']
            method()
            synced_count = self.sync_stats['total_synced'] - before_count
            print(f"✓ ({synced_count} records)")

        print(f"\n{'='*60}")
        print(f"Sync Complete!")
        print(f"Total Records Synced: {self.sync_stats['total_synced']}")

        if self.sync_stats['errors']:
            print(f"\nErrors ({len(self.sync_stats['errors'])}):")
            for error in self.sync_stats['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(self.sync_stats['errors']) > 10:
                print(f"  ... and {len(self.sync_stats['errors']) - 10} more errors")

        print(f"{'='*60}\n")

        return self.sync_stats


if __name__ == '__main__':
    syncer = DjangoToSheetsSync()
    syncer.run_full_sync()
