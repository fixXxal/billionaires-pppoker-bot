"""
Import Existing Data from Google Sheets to Django Database
This script migrates all existing data from Google Sheets to Django
Run this ONCE when setting up Django for the first time
"""

import os
import sys
import django
from datetime import datetime
from decimal import Decimal

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


class SheetsToDjango:
    """Import data from Google Sheets to Django database"""

    def __init__(self):
        credentials_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
        spreadsheet_name = os.getenv('SPREADSHEET_NAME', 'Billionaires_PPPoker_Bot')
        self.sheets = SheetsManager(credentials_file, spreadsheet_name)
        self.stats = {
            'imported': 0,
            'skipped': 0,
            'errors': []
        }

    def safe_decimal(self, value, default=0):
        """Safely convert to Decimal"""
        try:
            if value == '' or value is None:
                return Decimal(default)
            return Decimal(str(value))
        except:
            return Decimal(default)

    def safe_int(self, value, default=0):
        """Safely convert to int"""
        try:
            if value == '' or value is None:
                return default
            return int(value)
        except:
            return default

    def safe_date(self, value):
        """Safely parse date"""
        if not value or value == '':
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except:
            return None

    def safe_datetime(self, value):
        """Safely parse datetime"""
        if not value or value == '':
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except:
            try:
                return datetime.strptime(value, '%Y-%m-%d')
            except:
                return None

    def import_users(self):
        """Import Users from Google Sheets"""
        print("\n📥 Importing Users...")
        try:
            worksheet = self.sheets.spreadsheet.worksheet('Users')
            records = worksheet.get_all_records()

            for row in records:
                try:
                    telegram_id = self.safe_int(row.get('Telegram ID'))
                    if not telegram_id:
                        continue

                    user, created = User.objects.get_or_create(
                        telegram_id=telegram_id,
                        defaults={
                            'username': row.get('Username', ''),
                            'pppoker_id': row.get('PPPoker ID', ''),
                            'balance': self.safe_decimal(row.get('Balance', 0)),
                            'club_balance': self.safe_decimal(row.get('Club Balance', 0)),
                        }
                    )

                    if created:
                        self.stats['imported'] += 1
                        print(f"  ✓ Imported user: {user.username}")
                    else:
                        self.stats['skipped'] += 1

                except Exception as e:
                    self.stats['errors'].append(f"User import error: {str(e)}")

        except Exception as e:
            self.stats['errors'].append(f"Users sheet error: {str(e)}")

    def import_admins(self):
        """Import Admins from Google Sheets"""
        print("\n📥 Importing Admins...")
        try:
            worksheet = self.sheets.spreadsheet.worksheet('Admins')
            records = worksheet.get_all_records()

            for row in records:
                try:
                    telegram_id = self.safe_int(row.get('Telegram ID'))
                    if not telegram_id:
                        continue

                    admin, created = Admin.objects.get_or_create(
                        telegram_id=telegram_id,
                        defaults={
                            'username': row.get('Username', ''),
                            'role': row.get('Role', 'Admin'),
                            'is_active': row.get('Active', 'Yes') == 'Yes',
                        }
                    )

                    if created:
                        self.stats['imported'] += 1
                        print(f"  ✓ Imported admin: {admin.username} ({admin.role})")
                    else:
                        self.stats['skipped'] += 1

                except Exception as e:
                    self.stats['errors'].append(f"Admin import error: {str(e)}")

        except Exception as e:
            self.stats['errors'].append(f"Admins sheet error: {str(e)}")

    def import_payment_accounts(self):
        """Import Payment Accounts from Google Sheets"""
        print("\n📥 Importing Payment Accounts...")
        try:
            worksheet = self.sheets.spreadsheet.worksheet('Payment_Accounts')
            records = worksheet.get_all_records()

            for row in records:
                try:
                    method = row.get('Method', '')
                    if not method:
                        continue

                    account, created = PaymentAccount.objects.get_or_create(
                        method=method,
                        defaults={
                            'account_name': row.get('Account Name', ''),
                            'account_number': row.get('Account Number', ''),
                            'is_active': row.get('Active', 'Yes') == 'Yes',
                        }
                    )

                    if created:
                        self.stats['imported'] += 1
                        print(f"  ✓ Imported payment account: {account.method} - {account.account_name}")
                    else:
                        self.stats['skipped'] += 1

                except Exception as e:
                    self.stats['errors'].append(f"Payment account import error: {str(e)}")

        except Exception as e:
            self.stats['errors'].append(f"Payment_Accounts sheet error: {str(e)}")

    def import_deposits(self):
        """Import Deposits from Google Sheets"""
        print("\n📥 Importing Deposits...")
        try:
            worksheet = self.sheets.spreadsheet.worksheet('Deposits')
            records = worksheet.get_all_records()

            for row in records:
                try:
                    telegram_id = self.safe_int(row.get('Telegram ID'))
                    if not telegram_id:
                        continue

                    # Get or create user
                    user, _ = User.objects.get_or_create(
                        telegram_id=telegram_id,
                        defaults={'username': row.get('Username', '')}
                    )

                    deposit, created = Deposit.objects.get_or_create(
                        user=user,
                        amount=self.safe_decimal(row.get('Amount', 0)),
                        created_at=self.safe_datetime(row.get('Created At')) or datetime.now(),
                        defaults={
                            'method': row.get('Method', ''),
                            'account_name': row.get('Account Name', ''),
                            'proof_image_path': row.get('Proof Image', ''),
                            'pppoker_id': row.get('PPPoker ID', ''),
                            'status': row.get('Status', 'Pending'),
                            'approved_at': self.safe_datetime(row.get('Approved At')),
                            'approved_by': self.safe_int(row.get('Approved By'), None),
                            'rejection_reason': row.get('Rejection Reason', ''),
                        }
                    )

                    if created:
                        self.stats['imported'] += 1
                        print(f"  ✓ Imported deposit: {deposit.id} - {user.username} - {deposit.amount}")
                    else:
                        self.stats['skipped'] += 1

                except Exception as e:
                    self.stats['errors'].append(f"Deposit import error: {str(e)}")

        except Exception as e:
            self.stats['errors'].append(f"Deposits sheet error: {str(e)}")

    def import_withdrawals(self):
        """Import Withdrawals from Google Sheets"""
        print("\n📥 Importing Withdrawals...")
        try:
            worksheet = self.sheets.spreadsheet.worksheet('Withdrawals')
            records = worksheet.get_all_records()

            for row in records:
                try:
                    telegram_id = self.safe_int(row.get('Telegram ID'))
                    if not telegram_id:
                        continue

                    user, _ = User.objects.get_or_create(
                        telegram_id=telegram_id,
                        defaults={'username': row.get('Username', '')}
                    )

                    withdrawal, created = Withdrawal.objects.get_or_create(
                        user=user,
                        amount=self.safe_decimal(row.get('Amount', 0)),
                        created_at=self.safe_datetime(row.get('Created At')) or datetime.now(),
                        defaults={
                            'method': row.get('Method', ''),
                            'account_name': row.get('Account Name', ''),
                            'account_number': row.get('Account Number', ''),
                            'pppoker_id': row.get('PPPoker ID', ''),
                            'status': row.get('Status', 'Pending'),
                            'approved_at': self.safe_datetime(row.get('Approved At')),
                            'approved_by': self.safe_int(row.get('Approved By'), None),
                            'rejection_reason': row.get('Rejection Reason', ''),
                        }
                    )

                    if created:
                        self.stats['imported'] += 1
                        print(f"  ✓ Imported withdrawal: {withdrawal.id} - {user.username} - {withdrawal.amount}")
                    else:
                        self.stats['skipped'] += 1

                except Exception as e:
                    self.stats['errors'].append(f"Withdrawal import error: {str(e)}")

        except Exception as e:
            self.stats['errors'].append(f"Withdrawals sheet error: {str(e)}")

    def import_spin_users(self):
        """Import Spin Users from Google Sheets"""
        print("\n📥 Importing Spin Users...")
        try:
            worksheet = self.sheets.spreadsheet.worksheet('Spin_Users')
            records = worksheet.get_all_records()

            for row in records:
                try:
                    telegram_id = self.safe_int(row.get('Telegram ID'))
                    if not telegram_id:
                        continue

                    user, _ = User.objects.get_or_create(
                        telegram_id=telegram_id,
                        defaults={'username': row.get('Username', '')}
                    )

                    spin_user, created = SpinUser.objects.get_or_create(
                        user=user,
                        defaults={
                            'available_spins': self.safe_int(row.get('Available Spins', 0)),
                            'total_spins_used': self.safe_int(row.get('Total Spins Used', 0)),
                            'total_chips_earned': self.safe_int(row.get('Total Chips Earned', 0)),
                        }
                    )

                    if created:
                        self.stats['imported'] += 1
                        print(f"  ✓ Imported spin user: {user.username} - {spin_user.available_spins} spins")
                    else:
                        self.stats['skipped'] += 1

                except Exception as e:
                    self.stats['errors'].append(f"Spin user import error: {str(e)}")

        except Exception as e:
            self.stats['errors'].append(f"Spin_Users sheet error: {str(e)}")

    def run_import(self):
        """Run complete import"""
        print("="*70)
        print("GOOGLE SHEETS TO DJANGO DATABASE IMPORT")
        print("="*70)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Import in order (users first, then related records)
        self.import_users()
        self.import_admins()
        self.import_payment_accounts()
        self.import_spin_users()
        self.import_deposits()
        self.import_withdrawals()

        print("\n" + "="*70)
        print("IMPORT SUMMARY")
        print("="*70)
        print(f"✓ Records Imported: {self.stats['imported']}")
        print(f"⊘ Records Skipped: {self.stats['skipped']}")

        if self.stats['errors']:
            print(f"\n⚠ Errors ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:10]:
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more errors")

        print("="*70)
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)


if __name__ == '__main__':
    importer = SheetsToDjango()
    importer.run_import()
