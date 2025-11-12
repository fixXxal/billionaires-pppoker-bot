"""
Google Sheets Manager for Billionaires PPPoker Bot
Handles all data storage and retrieval operations
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import os
import json
from typing import Dict, List, Optional


class SheetsManager:
    """Manages all Google Sheets operations for the bot"""

    def __init__(self, credentials_file: str, spreadsheet_name: str, timezone: str = 'Indian/Maldives'):
        """Initialize the sheets manager"""
        self.timezone = pytz.timezone(timezone)
        self.spreadsheet_name = spreadsheet_name

        # Setup Google Sheets API
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]

        # Check if credentials are provided as environment variable (for Railway deployment)
        google_creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')

        if google_creds_json:
            # Use credentials from environment variable
            try:
                creds_dict = json.loads(google_creds_json)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            except json.JSONDecodeError as e:
                print(f"Error parsing GOOGLE_CREDENTIALS_JSON: {e}")
                raise
        else:
            # Use credentials from file (for local development)
            creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)

        self.client = gspread.authorize(creds)

        # Open or create spreadsheet
        try:
            self.spreadsheet = self.client.open(spreadsheet_name)
        except gspread.SpreadsheetNotFound:
            self.spreadsheet = self.client.create(spreadsheet_name)

        # Initialize worksheets
        self._init_worksheets()

    def _init_worksheets(self):
        """Initialize all required worksheets with headers"""

        # Users worksheet
        try:
            self.users_sheet = self.spreadsheet.worksheet('Users')
        except gspread.WorksheetNotFound:
            self.users_sheet = self.spreadsheet.add_worksheet(title='Users', rows=1000, cols=10)
            self.users_sheet.append_row([
                'User ID', 'Username', 'First Name', 'Last Name',
                'PPPoker ID', 'Registered At', 'Status', 'Account Name'
            ])

        # Deposits worksheet
        try:
            self.deposits_sheet = self.spreadsheet.worksheet('Deposits')
        except gspread.WorksheetNotFound:
            self.deposits_sheet = self.spreadsheet.add_worksheet(title='Deposits', rows=1000, cols=15)
            self.deposits_sheet.append_row([
                'Request ID', 'User ID', 'Username', 'PPPoker ID',
                'Amount', 'Payment Method', 'Account Name', 'Transaction ID/Slip',
                'Status', 'Requested At', 'Processed At', 'Processed By', 'Notes'
            ])

        # Withdrawals worksheet
        try:
            self.withdrawals_sheet = self.spreadsheet.worksheet('Withdrawals')
        except gspread.WorksheetNotFound:
            self.withdrawals_sheet = self.spreadsheet.add_worksheet(title='Withdrawals', rows=1000, cols=15)
            self.withdrawals_sheet.append_row([
                'Request ID', 'User ID', 'Username', 'PPPoker ID',
                'Amount', 'Payment Method', 'Account Name', 'Account Number',
                'Status', 'Requested At', 'Processed At', 'Processed By', 'Notes'
            ])

        # Join Requests worksheet
        try:
            self.join_requests_sheet = self.spreadsheet.worksheet('Join Requests')
        except gspread.WorksheetNotFound:
            self.join_requests_sheet = self.spreadsheet.add_worksheet(title='Join Requests', rows=1000, cols=10)
            self.join_requests_sheet.append_row([
                'Request ID', 'User ID', 'Username', 'First Name', 'Last Name',
                'PPPoker ID', 'Status', 'Requested At', 'Processed At', 'Processed By'
            ])

        # Payment Accounts worksheet
        try:
            self.payment_accounts_sheet = self.spreadsheet.worksheet('Payment Accounts')
        except gspread.WorksheetNotFound:
            self.payment_accounts_sheet = self.spreadsheet.add_worksheet(title='Payment Accounts', rows=10, cols=4)
            self.payment_accounts_sheet.append_row(['Payment Method', 'Account Number', 'Account Holder Name', 'Updated At'])
            # Initialize with default values
            self.payment_accounts_sheet.append_row(['BML', os.getenv('BML_ACCOUNT', ''), '', self._get_timestamp()])
            self.payment_accounts_sheet.append_row(['MIB', os.getenv('MIB_ACCOUNT', ''), '', self._get_timestamp()])
            self.payment_accounts_sheet.append_row(['USD', '', '', self._get_timestamp()])
            self.payment_accounts_sheet.append_row(['USDT', os.getenv('USDT_WALLET', ''), '', self._get_timestamp()])

        # Admins worksheet
        try:
            self.admins_sheet = self.spreadsheet.worksheet('Admins')
        except gspread.WorksheetNotFound:
            self.admins_sheet = self.spreadsheet.add_worksheet(title='Admins', rows=100, cols=5)
            self.admins_sheet.append_row(['Admin ID', 'Username', 'Name', 'Added By', 'Added At'])

        # Exchange Rates worksheet
        try:
            self.exchange_rates_sheet = self.spreadsheet.worksheet('Exchange Rates')
        except gspread.WorksheetNotFound:
            self.exchange_rates_sheet = self.spreadsheet.add_worksheet(title='Exchange Rates', rows=10, cols=3)
            self.exchange_rates_sheet.append_row(['Currency', 'Rate to MVR', 'Updated At'])
            # Initialize with default rates
            self.exchange_rates_sheet.append_row(['USD', '15.40', self._get_timestamp()])
            self.exchange_rates_sheet.append_row(['USDT', '15.40', self._get_timestamp()])

        # Promotions worksheet
        try:
            self.promotions_sheet = self.spreadsheet.worksheet('Promotions')
        except gspread.WorksheetNotFound:
            self.promotions_sheet = self.spreadsheet.add_worksheet(title='Promotions', rows=100, cols=7)
            self.promotions_sheet.append_row([
                'Promotion ID', 'Bonus Percentage', 'Start Date', 'End Date',
                'Status', 'Created By', 'Created At'
            ])

        # Promotion Eligibility worksheet (tracks who has received bonus)
        try:
            self.promotion_eligibility_sheet = self.spreadsheet.worksheet('Promotion Eligibility')
        except gspread.WorksheetNotFound:
            self.promotion_eligibility_sheet = self.spreadsheet.add_worksheet(title='Promotion Eligibility', rows=1000, cols=8)
            self.promotion_eligibility_sheet.append_row([
                'User ID', 'PPPoker ID', 'Promotion ID', 'Deposit Request ID',
                'Deposit Amount', 'Bonus Amount', 'Bonus Received At', 'Notes'
            ])

    def _get_timestamp(self) -> str:
        """Get current timestamp in the configured timezone"""
        return datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')

    def _generate_request_id(self, prefix: str) -> str:
        """Generate a unique request ID"""
        timestamp = datetime.now(self.timezone).strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"

    # User Management
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user data by user ID"""
        try:
            cell = self.users_sheet.find(str(user_id))
            if cell:
                row_data = self.users_sheet.row_values(cell.row)
                return {
                    'user_id': row_data[0],
                    'username': row_data[1],
                    'first_name': row_data[2],
                    'last_name': row_data[3],
                    'pppoker_id': row_data[4] if len(row_data) > 4 else None,
                    'registered_at': row_data[5] if len(row_data) > 5 else None,
                    'status': row_data[6] if len(row_data) > 6 else 'active',
                    'account_name': row_data[7] if len(row_data) > 7 else None,
                }
        except Exception:
            pass
        return None

    def create_or_update_user(self, user_id: int, username: str, first_name: str,
                             last_name: str, pppoker_id: str = None, account_name: str = None):
        """Create a new user or update existing user"""
        existing_user = self.get_user(user_id)

        if existing_user:
            # Update existing user
            cell = self.users_sheet.find(str(user_id))
            row = cell.row
            if pppoker_id:
                self.users_sheet.update_cell(row, 5, pppoker_id)
            if account_name:
                self.users_sheet.update_cell(row, 8, account_name)
        else:
            # Create new user
            self.users_sheet.append_row([
                user_id, username or '', first_name or '', last_name or '',
                pppoker_id or '', self._get_timestamp(), 'active', account_name or ''
            ])

    def update_user_pppoker_id(self, user_id: int, pppoker_id: str):
        """Update user's PPPoker ID"""
        cell = self.users_sheet.find(str(user_id))
        if cell:
            self.users_sheet.update_cell(cell.row, 5, pppoker_id)

    def update_user_account_name(self, user_id: int, account_name: str):
        """Update user's account name"""
        cell = self.users_sheet.find(str(user_id))
        if cell:
            self.users_sheet.update_cell(cell.row, 8, account_name)

    def get_all_user_ids(self) -> List[int]:
        """Get all user IDs from the Users sheet"""
        try:
            # Get all values from the Users sheet
            all_values = self.users_sheet.get_all_values()

            # Skip header row (index 0) and extract user IDs from column A
            user_ids = []
            for row in all_values[1:]:  # Skip header
                if row and row[0]:  # Check if user_id exists
                    try:
                        user_id = int(row[0])
                        user_ids.append(user_id)
                    except (ValueError, IndexError):
                        continue

            return user_ids
        except Exception as e:
            print(f"Error getting user IDs: {e}")
            return []

    # Deposit Management
    def create_deposit_request(self, user_id: int, username: str, pppoker_id: str,
                              amount: float, payment_method: str, account_name: str,
                              transaction_ref: str) -> str:
        """Create a new deposit request"""
        request_id = self._generate_request_id('DEP')
        self.deposits_sheet.append_row([
            request_id, user_id, username or '', pppoker_id, amount,
            payment_method, account_name, transaction_ref, 'Pending',
            self._get_timestamp(), '', '', ''
        ])
        return request_id

    def get_deposit_request(self, request_id: str) -> Optional[Dict]:
        """Get deposit request by ID"""
        try:
            cell = self.deposits_sheet.find(request_id)
            if cell:
                row_data = self.deposits_sheet.row_values(cell.row)
                return {
                    'request_id': row_data[0],
                    'user_id': int(row_data[1]),
                    'username': row_data[2],
                    'pppoker_id': row_data[3],
                    'amount': row_data[4],
                    'payment_method': row_data[5],
                    'account_name': row_data[6],
                    'transaction_ref': row_data[7],
                    'status': row_data[8],
                    'row': cell.row
                }
        except Exception:
            pass
        return None

    def update_deposit_status(self, request_id: str, status: str, admin_id: int, notes: str = ''):
        """Update deposit request status"""
        deposit = self.get_deposit_request(request_id)
        if deposit:
            row = deposit['row']
            self.deposits_sheet.update_cell(row, 9, status)  # Status
            self.deposits_sheet.update_cell(row, 11, self._get_timestamp())  # Processed At
            self.deposits_sheet.update_cell(row, 12, admin_id)  # Processed By
            self.deposits_sheet.update_cell(row, 13, notes)  # Notes

    # Withdrawal Management
    def create_withdrawal_request(self, user_id: int, username: str, pppoker_id: str,
                                 amount: float, payment_method: str, account_name: str,
                                 account_number: str) -> str:
        """Create a new withdrawal request"""
        request_id = self._generate_request_id('WDW')
        self.withdrawals_sheet.append_row([
            request_id, user_id, username or '', pppoker_id, amount,
            payment_method, account_name, account_number, 'Pending',
            self._get_timestamp(), '', '', ''
        ])
        return request_id

    def get_withdrawal_request(self, request_id: str) -> Optional[Dict]:
        """Get withdrawal request by ID"""
        try:
            cell = self.withdrawals_sheet.find(request_id)
            if cell:
                row_data = self.withdrawals_sheet.row_values(cell.row)
                return {
                    'request_id': row_data[0],
                    'user_id': int(row_data[1]),
                    'username': row_data[2],
                    'pppoker_id': row_data[3],
                    'amount': row_data[4],
                    'payment_method': row_data[5],
                    'account_name': row_data[6],
                    'account_number': row_data[7],
                    'status': row_data[8],
                    'row': cell.row
                }
        except Exception:
            pass
        return None

    def update_withdrawal_status(self, request_id: str, status: str, admin_id: int, notes: str = ''):
        """Update withdrawal request status"""
        withdrawal = self.get_withdrawal_request(request_id)
        if withdrawal:
            row = withdrawal['row']
            self.withdrawals_sheet.update_cell(row, 9, status)  # Status
            self.withdrawals_sheet.update_cell(row, 11, self._get_timestamp())  # Processed At
            self.withdrawals_sheet.update_cell(row, 12, admin_id)  # Processed By
            self.withdrawals_sheet.update_cell(row, 13, notes)  # Notes

    # Join Request Management
    def create_join_request(self, user_id: int, username: str, first_name: str,
                           last_name: str, pppoker_id: str) -> str:
        """Create a new join request"""
        request_id = self._generate_request_id('JOIN')
        self.join_requests_sheet.append_row([
            request_id, user_id, username or '', first_name or '', last_name or '',
            pppoker_id, 'Pending', self._get_timestamp(), '', ''
        ])
        return request_id

    def get_join_request(self, request_id: str) -> Optional[Dict]:
        """Get join request by ID"""
        try:
            cell = self.join_requests_sheet.find(request_id)
            if cell:
                row_data = self.join_requests_sheet.row_values(cell.row)
                return {
                    'request_id': row_data[0],
                    'user_id': int(row_data[1]),
                    'username': row_data[2],
                    'first_name': row_data[3],
                    'last_name': row_data[4],
                    'pppoker_id': row_data[5],
                    'status': row_data[6],
                    'row': cell.row
                }
        except Exception:
            pass
        return None

    def update_join_request_status(self, request_id: str, status: str, admin_id: int):
        """Update join request status"""
        join_req = self.get_join_request(request_id)
        if join_req:
            row = join_req['row']
            self.join_requests_sheet.update_cell(row, 7, status)  # Status
            self.join_requests_sheet.update_cell(row, 9, self._get_timestamp())  # Processed At
            self.join_requests_sheet.update_cell(row, 10, admin_id)  # Processed By

    # Payment Account Management
    def get_payment_account(self, method: str) -> Optional[str]:
        """Get payment account number for a specific method"""
        try:
            cell = self.payment_accounts_sheet.find(method)
            if cell:
                row_data = self.payment_accounts_sheet.row_values(cell.row)
                return row_data[1] if len(row_data) > 1 else None
        except Exception:
            pass
        return None

    def get_payment_account_holder(self, method: str) -> Optional[str]:
        """Get payment account holder name for a specific method"""
        try:
            cell = self.payment_accounts_sheet.find(method)
            if cell:
                row_data = self.payment_accounts_sheet.row_values(cell.row)
                return row_data[2] if len(row_data) > 2 else None
        except Exception:
            pass
        return None

    def get_payment_account_details(self, method: str) -> Optional[Dict]:
        """Get complete payment account details for a specific method"""
        try:
            cell = self.payment_accounts_sheet.find(method)
            if cell:
                row_data = self.payment_accounts_sheet.row_values(cell.row)
                return {
                    'method': row_data[0],
                    'account_number': row_data[1] if len(row_data) > 1 else None,
                    'account_holder': row_data[2] if len(row_data) > 2 else None,
                    'updated_at': row_data[3] if len(row_data) > 3 else None
                }
        except Exception:
            pass
        return None

    def update_payment_account(self, method: str, account_number: str, account_holder: str = None):
        """Update payment account number and holder name"""
        try:
            cell = self.payment_accounts_sheet.find(method)
            if cell:
                row = cell.row
                # Format the cell as TEXT to prevent scientific notation for long numbers
                self.payment_accounts_sheet.format(f'B{row}', {'numberFormat': {'type': 'TEXT'}})
                # Update with raw value (no apostrophe needed)
                self.payment_accounts_sheet.update_cell(row, 2, account_number)
                if account_holder:
                    self.payment_accounts_sheet.update_cell(row, 3, account_holder)
                self.payment_accounts_sheet.update_cell(row, 4, self._get_timestamp())
            else:
                # Add new payment method - append row first
                self.payment_accounts_sheet.append_row([method, account_number, account_holder or '', self._get_timestamp()])
                # Find the row we just added and format it
                new_cell = self.payment_accounts_sheet.find(method)
                if new_cell:
                    self.payment_accounts_sheet.format(f'B{new_cell.row}', {'numberFormat': {'type': 'TEXT'}})
        except Exception as e:
            # Add new payment method as fallback
            self.payment_accounts_sheet.append_row([method, account_number, account_holder or '', self._get_timestamp()])

    def clear_payment_account(self, method: str) -> bool:
        """Clear/remove a payment account"""
        try:
            cell = self.payment_accounts_sheet.find(method)
            if cell:
                row = cell.row
                # Clear account number and holder name (keep method name)
                self.payment_accounts_sheet.update_cell(row, 2, '')  # Clear account number
                self.payment_accounts_sheet.update_cell(row, 3, '')  # Clear holder name
                self.payment_accounts_sheet.update_cell(row, 4, self._get_timestamp())  # Update timestamp
                return True
            return False
        except Exception as e:
            print(f"Error clearing payment account: {e}")
            return False

    def get_all_payment_accounts(self) -> Dict[str, Dict]:
        """Get all payment accounts with details"""
        accounts = {}
        rows = self.payment_accounts_sheet.get_all_values()[1:]  # Skip header
        for row in rows:
            if len(row) >= 2 and row[0] and row[1]:
                accounts[row[0]] = {
                    'account_number': row[1],
                    'account_holder': row[2] if len(row) > 2 else None,
                    'updated_at': row[3] if len(row) > 3 else None
                }
        return accounts

    # Admin Management
    def add_admin(self, admin_id: int, username: str, name: str, added_by: int) -> bool:
        """Add a new admin to the system"""
        try:
            # Check if admin already exists
            try:
                cell = self.admins_sheet.find(str(admin_id))
                if cell:
                    return False  # Admin already exists
            except Exception:
                pass  # Admin doesn't exist, continue to add

            # Add new admin
            self.admins_sheet.append_row([
                admin_id,
                username or '',
                name or '',
                added_by,
                self._get_timestamp()
            ])
            return True
        except Exception as e:
            print(f"Error adding admin: {e}")
            return False

    def remove_admin(self, admin_id: int) -> bool:
        """Remove an admin from the system"""
        try:
            cell = self.admins_sheet.find(str(admin_id))
            if cell:
                self.admins_sheet.delete_rows(cell.row)
                return True
            return False
        except Exception as e:
            print(f"Error removing admin: {e}")
            return False

    def get_all_admins(self) -> List[Dict]:
        """Get list of all admins"""
        admins = []
        try:
            all_rows = self.admins_sheet.get_all_values()[1:]  # Skip header
            for row in all_rows:
                if len(row) >= 5 and row[0]:
                    admins.append({
                        'admin_id': int(row[0]),
                        'username': row[1] if len(row) > 1 else '',
                        'name': row[2] if len(row) > 2 else '',
                        'added_by': row[3] if len(row) > 3 else '',
                        'added_at': row[4] if len(row) > 4 else ''
                    })
        except Exception as e:
            print(f"Error getting admins: {e}")
        return admins

    def is_admin(self, user_id: int, super_admin_id: int) -> bool:
        """Check if user is super admin or regular admin"""
        # Check if super admin
        if user_id == super_admin_id:
            return True

        # Check if in admins list
        try:
            cell = self.admins_sheet.find(str(user_id))
            return cell is not None
        except Exception:
            return False

    # Statistics and Reporting
    def get_deposits_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get all approved deposits within date range"""
        deposits = []
        try:
            all_rows = self.deposits_sheet.get_all_values()[1:]  # Skip header

            for row in all_rows:
                if len(row) < 11:
                    continue

                status = row[8] if len(row) > 8 else ''
                if status != 'Approved':
                    continue

                # Parse date (column 10 - Processed At)
                processed_at = row[10] if len(row) > 10 else ''
                if not processed_at:
                    continue

                try:
                    # Parse date format: YYYY-MM-DD HH:MM:SS
                    row_date = datetime.strptime(processed_at, '%Y-%m-%d %H:%M:%S')
                    row_date = self.timezone.localize(row_date)

                    if start_date <= row_date <= end_date:
                        deposits.append({
                            'request_id': row[0],
                            'amount': float(row[4]) if row[4] else 0,
                            'method': row[5],
                            'processed_at': processed_at
                        })
                except (ValueError, IndexError):
                    continue

        except Exception as e:
            print(f"Error getting deposits by date: {e}")

        return deposits

    def get_withdrawals_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get all completed withdrawals within date range"""
        withdrawals = []
        try:
            all_rows = self.withdrawals_sheet.get_all_values()[1:]  # Skip header

            for row in all_rows:
                if len(row) < 11:
                    continue

                status = row[8] if len(row) > 8 else ''
                if status != 'Completed':
                    continue

                # Parse date (column 10 - Processed At)
                processed_at = row[10] if len(row) > 10 else ''
                if not processed_at:
                    continue

                try:
                    # Parse date format: YYYY-MM-DD HH:MM:SS
                    row_date = datetime.strptime(processed_at, '%Y-%m-%d %H:%M:%S')
                    row_date = self.timezone.localize(row_date)

                    if start_date <= row_date <= end_date:
                        withdrawals.append({
                            'request_id': row[0],
                            'amount': float(row[4]) if row[4] else 0,
                            'method': row[5],
                            'processed_at': processed_at
                        })
                except (ValueError, IndexError):
                    continue

        except Exception as e:
            print(f"Error getting withdrawals by date: {e}")

        return withdrawals

    # Exchange Rate Management
    def set_exchange_rate(self, currency: str, rate: float) -> bool:
        """Set or update exchange rate for a currency"""
        try:
            cell = self.exchange_rates_sheet.find(currency)
            if cell:
                # Update existing rate
                row = cell.row
                self.exchange_rates_sheet.update_cell(row, 2, str(rate))
                self.exchange_rates_sheet.update_cell(row, 3, self._get_timestamp())
                return True
            else:
                # Add new currency rate
                self.exchange_rates_sheet.append_row([currency, str(rate), self._get_timestamp()])
                return True
        except Exception as e:
            print(f"Error setting exchange rate: {e}")
            return False

    def get_exchange_rate(self, currency: str) -> Optional[float]:
        """Get exchange rate for a currency"""
        try:
            cell = self.exchange_rates_sheet.find(currency)
            if cell:
                row_data = self.exchange_rates_sheet.row_values(cell.row)
                if len(row_data) > 1 and row_data[1]:
                    return float(row_data[1])
        except Exception as e:
            print(f"Error getting exchange rate: {e}")
        return None

    def get_all_exchange_rates(self) -> Dict[str, Dict]:
        """Get all exchange rates"""
        rates = {}
        try:
            all_rows = self.exchange_rates_sheet.get_all_values()[1:]  # Skip header
            for row in all_rows:
                if len(row) >= 2 and row[0] and row[1]:
                    rates[row[0]] = {
                        'rate': float(row[1]),
                        'updated_at': row[2] if len(row) > 2 else None
                    }
        except Exception as e:
            print(f"Error getting all exchange rates: {e}")
        return rates

    # Promotion Management
    def create_promotion(self, bonus_percentage: float, start_date: str, end_date: str, admin_id: int) -> Optional[str]:
        """Create a new promotion"""
        try:
            # Generate promotion ID
            promotion_id = f"PROMO{datetime.now(self.timezone).strftime('%Y%m%d%H%M%S')}"

            # Deactivate any existing active promotions
            self._deactivate_all_promotions()

            # Add new promotion
            self.promotions_sheet.append_row([
                promotion_id,
                str(bonus_percentage),
                start_date,
                end_date,
                'Active',
                str(admin_id),
                self._get_timestamp()
            ])

            return promotion_id
        except Exception as e:
            print(f"Error creating promotion: {e}")
            return None

    def _deactivate_all_promotions(self):
        """Deactivate all existing promotions"""
        try:
            all_rows = self.promotions_sheet.get_all_values()[1:]  # Skip header
            for idx, row in enumerate(all_rows, start=2):
                if len(row) > 4 and row[4] == 'Active':
                    self.promotions_sheet.update_cell(idx, 5, 'Inactive')
        except Exception as e:
            print(f"Error deactivating promotions: {e}")

    def get_active_promotion(self) -> Optional[Dict]:
        """Get the currently active promotion"""
        try:
            now = datetime.now(self.timezone)
            all_rows = self.promotions_sheet.get_all_values()[1:]  # Skip header

            for row in all_rows:
                if len(row) >= 5 and row[4] == 'Active':
                    # Parse dates
                    try:
                        start_date = datetime.strptime(row[2], '%Y-%m-%d')
                        end_date = datetime.strptime(row[3], '%Y-%m-%d')

                        # Make them timezone-aware
                        start_date = self.timezone.localize(start_date)
                        end_date = self.timezone.localize(end_date.replace(hour=23, minute=59, second=59))

                        # Check if promotion is currently valid
                        if start_date <= now <= end_date:
                            return {
                                'promotion_id': row[0],
                                'bonus_percentage': float(row[1]),
                                'start_date': row[2],
                                'end_date': row[3],
                                'status': row[4],
                                'created_by': row[5] if len(row) > 5 else '',
                                'created_at': row[6] if len(row) > 6 else ''
                            }
                    except ValueError as e:
                        print(f"Error parsing promotion dates: {e}")
                        continue

        except Exception as e:
            print(f"Error getting active promotion: {e}")
        return None

    def get_all_promotions(self) -> List[Dict]:
        """Get all promotions"""
        promotions = []
        try:
            all_rows = self.promotions_sheet.get_all_values()[1:]  # Skip header
            for row in all_rows:
                if len(row) >= 5 and row[0]:
                    promotions.append({
                        'promotion_id': row[0],
                        'bonus_percentage': float(row[1]) if row[1] else 0,
                        'start_date': row[2],
                        'end_date': row[3],
                        'status': row[4],
                        'created_by': row[5] if len(row) > 5 else '',
                        'created_at': row[6] if len(row) > 6 else ''
                    })
        except Exception as e:
            print(f"Error getting all promotions: {e}")
        return promotions

    def update_promotion(self, promotion_id: str, bonus_percentage: Optional[float] = None,
                        start_date: Optional[str] = None, end_date: Optional[str] = None) -> bool:
        """Update an existing promotion"""
        try:
            cell = self.promotions_sheet.find(promotion_id)
            if cell:
                row = cell.row
                if bonus_percentage is not None:
                    self.promotions_sheet.update_cell(row, 2, str(bonus_percentage))
                if start_date is not None:
                    self.promotions_sheet.update_cell(row, 3, start_date)
                if end_date is not None:
                    self.promotions_sheet.update_cell(row, 4, end_date)
                return True
        except Exception as e:
            print(f"Error updating promotion: {e}")
        return False

    def deactivate_promotion(self, promotion_id: str) -> bool:
        """Deactivate a specific promotion"""
        try:
            cell = self.promotions_sheet.find(promotion_id)
            if cell:
                self.promotions_sheet.update_cell(cell.row, 5, 'Inactive')
                return True
        except Exception as e:
            print(f"Error deactivating promotion: {e}")
        return False

    def check_user_promotion_eligibility(self, user_id: int, pppoker_id: str, promotion_id: str) -> bool:
        """Check if user is eligible for promotion (hasn't received bonus for this promotion yet)"""
        try:
            all_rows = self.promotion_eligibility_sheet.get_all_values()[1:]  # Skip header
            for row in all_rows:
                if len(row) >= 3:
                    # Check if user already received bonus for this promotion
                    if row[0] == str(user_id) and row[2] == promotion_id:
                        return False
            return True
        except Exception as e:
            print(f"Error checking promotion eligibility: {e}")
            return False

    def record_promotion_bonus(self, user_id: int, pppoker_id: str, promotion_id: str,
                              deposit_request_id: str, deposit_amount: float, bonus_amount: float) -> bool:
        """Record that a user has received a promotion bonus"""
        try:
            self.promotion_eligibility_sheet.append_row([
                str(user_id),
                pppoker_id,
                promotion_id,
                deposit_request_id,
                str(deposit_amount),
                str(bonus_amount),
                self._get_timestamp(),
                'Bonus applied on first deposit during promotion period'
            ])
            return True
        except Exception as e:
            print(f"Error recording promotion bonus: {e}")
            return False

    def get_user_promotion_bonuses(self, user_id: int) -> List[Dict]:
        """Get all promotion bonuses received by a user"""
        bonuses = []
        try:
            all_rows = self.promotion_eligibility_sheet.get_all_values()[1:]  # Skip header
            for row in all_rows:
                if len(row) >= 6 and row[0] == str(user_id):
                    bonuses.append({
                        'pppoker_id': row[1],
                        'promotion_id': row[2],
                        'deposit_request_id': row[3],
                        'deposit_amount': float(row[4]) if row[4] else 0,
                        'bonus_amount': float(row[5]) if row[5] else 0,
                        'received_at': row[6] if len(row) > 6 else '',
                        'notes': row[7] if len(row) > 7 else ''
                    })
        except Exception as e:
            print(f"Error getting user promotion bonuses: {e}")
        return bonuses
