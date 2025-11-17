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

        # Seat Requests worksheet
        try:
            self.seat_requests_sheet = self.spreadsheet.worksheet('Seat Requests')
        except gspread.WorksheetNotFound:
            self.seat_requests_sheet = self.spreadsheet.add_worksheet(title='Seat Requests', rows=1000, cols=15)
            self.seat_requests_sheet.append_row([
                'Request ID', 'User ID', 'Username', 'PPPoker ID',
                'Amount', 'Payment Method', 'Transaction ID/Slip',
                'Status', 'Requested At', 'Approved At', 'Settled At',
                'Processed By', 'Has Credit', 'Notes'
            ])

        # User Credits worksheet (tracks users with pending credits)
        try:
            self.user_credits_sheet = self.spreadsheet.worksheet('User Credits')
        except gspread.WorksheetNotFound:
            self.user_credits_sheet = self.spreadsheet.add_worksheet(title='User Credits', rows=1000, cols=8)
            self.user_credits_sheet.append_row([
                'User ID', 'Username', 'PPPoker ID', 'Credit Amount',
                'Seat Request ID', 'Created At', 'Reminder Count', 'Status'
            ])

        # Daily Reports worksheet (tracks TODAY only)
        try:
            self.daily_reports_sheet = self.spreadsheet.worksheet('Daily Reports')
        except gspread.WorksheetNotFound:
            self.daily_reports_sheet = self.spreadsheet.add_worksheet(title='Daily Reports', rows=1000, cols=15)
            self.daily_reports_sheet.append_row([
                'Report Date', 'Report Time',
                'MVR Deposits', 'MVR Withdrawals', 'MVR Profit',
                'USD Deposits', 'USD Withdrawals', 'USD Profit',
                'USDT Deposits', 'USDT Withdrawals', 'USDT Profit',
                'Total Profit (MVR)',
                'Active Credits Count', 'Active Credits Amount',
                'Generated At'
            ])

        # Weekly Reports worksheet (tracks THIS WEEK only)
        try:
            self.weekly_reports_sheet = self.spreadsheet.worksheet('Weekly Reports')
        except gspread.WorksheetNotFound:
            self.weekly_reports_sheet = self.spreadsheet.add_worksheet(title='Weekly Reports', rows=1000, cols=15)
            self.weekly_reports_sheet.append_row([
                'Report Date', 'Report Time',
                'MVR Deposits', 'MVR Withdrawals', 'MVR Profit',
                'USD Deposits', 'USD Withdrawals', 'USD Profit',
                'USDT Deposits', 'USDT Withdrawals', 'USDT Profit',
                'Total Profit (MVR)',
                'Active Credits Count', 'Active Credits Amount',
                'Generated At'
            ])

        # Monthly Reports worksheet (tracks THIS MONTH only)
        try:
            self.monthly_reports_sheet = self.spreadsheet.worksheet('Monthly Reports')
        except gspread.WorksheetNotFound:
            self.monthly_reports_sheet = self.spreadsheet.add_worksheet(title='Monthly Reports', rows=1000, cols=15)
            self.monthly_reports_sheet.append_row([
                'Report Date', 'Report Time',
                'MVR Deposits', 'MVR Withdrawals', 'MVR Profit',
                'USD Deposits', 'USD Withdrawals', 'USD Profit',
                'USDT Deposits', 'USDT Withdrawals', 'USDT Profit',
                'Total Profit (MVR)',
                'Active Credits Count', 'Active Credits Amount',
                'Generated At'
            ])

        # 6 Months Reports worksheet (tracks 6 MONTHS only)
        try:
            self.six_months_reports_sheet = self.spreadsheet.worksheet('6 Months Reports')
        except gspread.WorksheetNotFound:
            self.six_months_reports_sheet = self.spreadsheet.add_worksheet(title='6 Months Reports', rows=1000, cols=15)
            self.six_months_reports_sheet.append_row([
                'Report Date', 'Report Time',
                'MVR Deposits', 'MVR Withdrawals', 'MVR Profit',
                'USD Deposits', 'USD Withdrawals', 'USD Profit',
                'USDT Deposits', 'USDT Withdrawals', 'USDT Profit',
                'Total Profit (MVR)',
                'Active Credits Count', 'Active Credits Amount',
                'Generated At'
            ])

        # Yearly Reports worksheet (tracks THIS YEAR only)
        try:
            self.yearly_reports_sheet = self.spreadsheet.worksheet('Yearly Reports')
        except gspread.WorksheetNotFound:
            self.yearly_reports_sheet = self.spreadsheet.add_worksheet(title='Yearly Reports', rows=1000, cols=15)
            self.yearly_reports_sheet.append_row([
                'Report Date', 'Report Time',
                'MVR Deposits', 'MVR Withdrawals', 'MVR Profit',
                'USD Deposits', 'USD Withdrawals', 'USD Profit',
                'USDT Deposits', 'USDT Withdrawals', 'USDT Profit',
                'Total Profit (MVR)',
                'Active Credits Count', 'Active Credits Amount',
                'Generated At'
            ])

        # Spin Users worksheet
        try:
            self.spin_users_sheet = self.spreadsheet.worksheet('Spin Users')
        except gspread.WorksheetNotFound:
            self.spin_users_sheet = self.spreadsheet.add_worksheet(title='Spin Users', rows=1000, cols=9)
            self.spin_users_sheet.append_row([
                'User ID', 'Username', 'Available Spins', 'Total Spins Used',
                'Total Chips Earned', 'Total Deposit (MVR)', 'Created At', 'Last Spin At', 'PPPoker ID'
            ])

        # Milestone Rewards worksheet
        try:
            self.milestone_rewards_sheet = self.spreadsheet.worksheet('Milestone Rewards')
        except gspread.WorksheetNotFound:
            self.milestone_rewards_sheet = self.spreadsheet.add_worksheet(title='Milestone Rewards', rows=1000, cols=10)
            self.milestone_rewards_sheet.append_row([
                'User ID', 'Username', 'Milestone Type', 'Milestone Count',
                'Chips Awarded', 'Triggered At Spin Count', 'Created At', 'Approved', 'Approved By', 'PPPoker ID'
            ])

        # Run migration to add PPPoker ID columns if they don't exist
        self._migrate_add_pppoker_columns()

    def _migrate_add_pppoker_columns(self):
        """Add PPPoker ID columns to existing sheets if they don't exist"""
        try:
            # Check and add to Spin Users sheet
            try:
                headers = self.spin_users_sheet.row_values(1)
                if len(headers) < 9 or 'PPPoker ID' not in headers:
                    print("🔄 Adding PPPoker ID column to Spin Users sheet...")
                    # Update header row to add PPPoker ID column
                    if len(headers) == 8:
                        self.spin_users_sheet.update_cell(1, 9, 'PPPoker ID')
                        print("✅ PPPoker ID column added to Spin Users sheet!")
            except Exception as e:
                print(f"Note: Could not add PPPoker ID to Spin Users: {e}")

            # Check and add to Milestone Rewards sheet
            try:
                headers = self.milestone_rewards_sheet.row_values(1)
                if len(headers) < 10 or 'PPPoker ID' not in headers:
                    print("🔄 Adding PPPoker ID column to Milestone Rewards sheet...")
                    # Update header row to add PPPoker ID column
                    if len(headers) == 9:
                        self.milestone_rewards_sheet.update_cell(1, 10, 'PPPoker ID')
                        print("✅ PPPoker ID column added to Milestone Rewards sheet!")
            except Exception as e:
                print(f"Note: Could not add PPPoker ID to Milestone Rewards: {e}")

        except Exception as e:
            print(f"Migration note: {e}")

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

    # Seat Request Functions
    def create_seat_request(self, user_id: int, username: str, pppoker_id: str, amount: float) -> str:
        """Create a new seat request"""
        try:
            import uuid
            request_id = f"SEAT_{uuid.uuid4().hex[:8].upper()}"

            self.seat_requests_sheet.append_row([
                request_id,
                str(user_id),
                username or '',
                pppoker_id,
                amount,
                '',  # Payment Method (filled after admin approval)
                '',  # Transaction ID/Slip
                'Pending',
                self._get_timestamp(),
                '',  # Approved At
                '',  # Settled At
                '',  # Processed By
                'No',  # Has Credit
                ''  # Notes
            ])
            return request_id
        except Exception as e:
            print(f"Error creating seat request: {e}")
            return None

    def get_seat_request(self, request_id: str) -> Optional[Dict]:
        """Get seat request by ID"""
        try:
            all_rows = self.seat_requests_sheet.get_all_values()[1:]
            print(f"Searching for seat request {request_id} in {len(all_rows)} rows")
            for row in all_rows:
                if len(row) > 0:
                    print(f"Checking row: {row[0]}")
                    if row[0] == request_id:
                        print(f"Found seat request {request_id}")
                        return {
                            'request_id': row[0],
                            'user_id': int(row[1]) if len(row) > 1 and row[1] else 0,
                            'username': row[2] if len(row) > 2 else '',
                            'pppoker_id': row[3] if len(row) > 3 else '',
                            'amount': float(row[4]) if len(row) > 4 and row[4] else 0,
                            'payment_method': row[5] if len(row) > 5 else '',
                            'transaction_id': row[6] if len(row) > 6 else '',
                            'status': row[7] if len(row) > 7 else 'Pending',
                            'requested_at': row[8] if len(row) > 8 else '',
                            'approved_at': row[9] if len(row) > 9 else '',
                            'settled_at': row[10] if len(row) > 10 else '',
                            'processed_by': row[11] if len(row) > 11 else '',
                            'has_credit': row[12] if len(row) > 12 else 'No',
                            'notes': row[13] if len(row) > 13 else ''
                        }
            print(f"Seat request {request_id} not found")
        except Exception as e:
            print(f"Error getting seat request: {e}")
            import traceback
            traceback.print_exc()
        return None

    def approve_seat_request(self, request_id: str, admin_id: int) -> bool:
        """Approve seat request"""
        try:
            cell = self.seat_requests_sheet.find(request_id)
            if cell:
                row_number = cell.row
                # Update status and approved_at
                self.seat_requests_sheet.update_cell(row_number, 8, 'Approved')
                self.seat_requests_sheet.update_cell(row_number, 10, self._get_timestamp())
                self.seat_requests_sheet.update_cell(row_number, 12, str(admin_id))
                return True
        except Exception as e:
            print(f"Error approving seat request: {e}")
        return False

    def reject_seat_request(self, request_id: str, admin_id: int, reason: str = '') -> bool:
        """Reject seat request"""
        try:
            cell = self.seat_requests_sheet.find(request_id)
            if cell:
                row_number = cell.row
                self.seat_requests_sheet.update_cell(row_number, 8, 'Rejected')
                self.seat_requests_sheet.update_cell(row_number, 12, str(admin_id))
                if reason:
                    self.seat_requests_sheet.update_cell(row_number, 14, reason)
                return True
        except Exception as e:
            print(f"Error rejecting seat request: {e}")
        return False

    def settle_seat_request(self, request_id: str, payment_method: str, transaction_id: str, admin_id: int) -> bool:
        """Mark seat request as settled after slip verification"""
        try:
            cell = self.seat_requests_sheet.find(request_id)
            if cell:
                row_number = cell.row
                self.seat_requests_sheet.update_cell(row_number, 6, payment_method)
                self.seat_requests_sheet.update_cell(row_number, 7, transaction_id)
                self.seat_requests_sheet.update_cell(row_number, 8, 'Settled')
                self.seat_requests_sheet.update_cell(row_number, 11, self._get_timestamp())
                self.seat_requests_sheet.update_cell(row_number, 12, str(admin_id))
                return True
        except Exception as e:
            print(f"Error settling seat request: {e}")
        return False

    # User Credit Functions
    def add_user_credit(self, user_id: int, username: str, pppoker_id: str, amount: float, seat_request_id: str) -> bool:
        """Add user to credits list"""
        try:
            self.user_credits_sheet.append_row([
                str(user_id),
                username or '',
                pppoker_id,
                amount,
                seat_request_id,
                self._get_timestamp(),
                '0',  # Reminder Count
                'Active'
            ])

            # Update seat request to mark has_credit
            cell = self.seat_requests_sheet.find(seat_request_id)
            if cell:
                self.seat_requests_sheet.update_cell(cell.row, 13, 'Yes')

            return True
        except Exception as e:
            print(f"Error adding user credit: {e}")
        return False

    def get_user_credit(self, user_id: int) -> Optional[Dict]:
        """Get active credit for user"""
        try:
            all_rows = self.user_credits_sheet.get_all_values()[1:]
            for row in all_rows:
                if len(row) >= 8 and row[0] == str(user_id) and row[7] == 'Active':
                    return {
                        'user_id': int(row[0]),
                        'username': row[1],
                        'pppoker_id': row[2],
                        'amount': float(row[3]) if row[3] else 0,
                        'seat_request_id': row[4],
                        'created_at': row[5],
                        'reminder_count': int(row[6]) if row[6] else 0,
                        'status': row[7]
                    }
        except Exception as e:
            print(f"Error getting user credit: {e}")
        return None

    def get_all_active_credits(self) -> List[Dict]:
        """Get all users with active credits"""
        try:
            credits = []
            all_rows = self.user_credits_sheet.get_all_values()[1:]
            for row in all_rows:
                if len(row) >= 8 and row[7] == 'Active':
                    credits.append({
                        'user_id': int(row[0]) if row[0] else 0,
                        'username': row[1],
                        'pppoker_id': row[2],
                        'amount': float(row[3]) if row[3] else 0,
                        'seat_request_id': row[4],
                        'created_at': row[5],
                        'reminder_count': int(row[6]) if row[6] else 0,
                        'status': row[7]
                    })
            return credits
        except Exception as e:
            print(f"Error getting active credits: {e}")
        return []

    def increment_credit_reminder(self, user_id: int) -> bool:
        """Increment reminder count for user credit"""
        try:
            all_rows = self.user_credits_sheet.get_all_values()
            for idx, row in enumerate(all_rows[1:], start=2):
                if len(row) >= 8 and row[0] == str(user_id) and row[7] == 'Active':
                    current_count = int(row[6]) if row[6] else 0
                    self.user_credits_sheet.update_cell(idx, 7, str(current_count + 1))
                    return True
        except Exception as e:
            print(f"Error incrementing credit reminder: {e}")
        return False

    def clear_user_credit(self, user_id: int) -> bool:
        """Clear user credit (mark as settled)"""
        try:
            all_rows = self.user_credits_sheet.get_all_values()
            for idx, row in enumerate(all_rows[1:], start=2):
                if len(row) >= 8 and row[0] == str(user_id) and row[7] == 'Active':
                    self.user_credits_sheet.update_cell(idx, 8, 'Settled')
                    return True
        except Exception as e:
            print(f"Error clearing user credit: {e}")
        return False

    def get_daily_credit_summary(self) -> Dict:
        """Get summary of all active credits for daily notification"""
        try:
            credits = self.get_all_active_credits()
            total_credit_amount = sum(credit['amount'] for credit in credits)
            credit_count = len(credits)

            # Get details for each credit
            credit_details = []
            for credit in credits:
                credit_details.append({
                    'username': credit['username'],
                    'pppoker_id': credit['pppoker_id'],
                    'amount': credit['amount'],
                    'created_at': credit['created_at']
                })

            return {
                'total_amount': total_credit_amount,
                'count': credit_count,
                'details': credit_details
            }
        except Exception as e:
            print(f"Error getting daily credit summary: {e}")
            return {
                'total_amount': 0,
                'count': 0,
                'details': []
            }

    def save_all_reports(self, all_reports_data: Dict) -> bool:
        """Save all period reports to their respective Google Sheets"""
        try:
            now = datetime.now(self.timezone)
            report_date = now.strftime('%Y-%m-%d')
            report_time = now.strftime('%H:%M:%S')
            timestamp = self._get_timestamp()

            # Helper function to create row
            def create_row(period_prefix):
                return [
                    report_date,
                    report_time,
                    all_reports_data.get(f'{period_prefix}_mvr_deposits', 0),
                    all_reports_data.get(f'{period_prefix}_mvr_withdrawals', 0),
                    all_reports_data.get(f'{period_prefix}_mvr_profit', 0),
                    all_reports_data.get(f'{period_prefix}_usd_deposits', 0),
                    all_reports_data.get(f'{period_prefix}_usd_withdrawals', 0),
                    all_reports_data.get(f'{period_prefix}_usd_profit', 0),
                    all_reports_data.get(f'{period_prefix}_usdt_deposits', 0),
                    all_reports_data.get(f'{period_prefix}_usdt_withdrawals', 0),
                    all_reports_data.get(f'{period_prefix}_usdt_profit', 0),
                    all_reports_data.get(f'{period_prefix}_total_profit', 0),
                    all_reports_data.get('credits_count', 0),
                    all_reports_data.get('credits_amount', 0),
                    timestamp
                ]

            # Save to Daily Reports
            self.daily_reports_sheet.append_row(create_row('today'))

            # Save to Weekly Reports
            self.weekly_reports_sheet.append_row(create_row('week'))

            # Save to Monthly Reports
            self.monthly_reports_sheet.append_row(create_row('month'))

            # Save to 6 Months Reports
            self.six_months_reports_sheet.append_row(create_row('six_months'))

            # Save to Yearly Reports
            self.yearly_reports_sheet.append_row(create_row('year'))

            return True
        except Exception as e:
            print(f"Error saving reports: {e}")
            return False

    # Spin Bot Methods

    def get_spin_user(self, user_id: int) -> Optional[Dict]:
        """Get spin user data"""
        try:
            cell = self.spin_users_sheet.find(str(user_id))
            if cell:
                row = self.spin_users_sheet.row_values(cell.row)
                return {
                    'user_id': int(row[0]),
                    'username': row[1] if len(row) > 1 else 'Unknown',
                    'available_spins': int(row[2]) if len(row) > 2 and row[2] else 0,
                    'total_spins_used': int(row[3]) if len(row) > 3 and row[3] else 0,
                    'total_chips_earned': int(row[4]) if len(row) > 4 and row[4] else 0,
                    'total_deposit': float(row[5]) if len(row) > 5 and row[5] else 0,
                    'created_at': row[6] if len(row) > 6 else '',
                    'last_spin_at': row[7] if len(row) > 7 else '',
                    'pppoker_id': row[8] if len(row) > 8 and row[8] else ''
                }
            return None
        except Exception as e:
            print(f"Error getting spin user: {e}")
            return None

    def create_spin_user(self, user_id: int, username: str, available_spins: int = 0, total_deposit: float = 0, pppoker_id: str = ''):
        """Create a new spin user"""
        try:
            self.spin_users_sheet.append_row([
                user_id,
                username,
                available_spins,
                0,  # total_spins_used
                0,  # total_chips_earned
                total_deposit,
                self._get_timestamp(),
                '',  # last_spin_at
                pppoker_id
            ])
            return True
        except Exception as e:
            print(f"Error creating spin user: {e}")
            return False

    def update_spin_user(self, user_id: int, username: str = None, available_spins: int = None,
                        total_spins_used: int = None, total_chips_earned: int = None,
                        total_deposit: float = None, pppoker_id: str = None):
        """Update spin user data"""
        try:
            cell = self.spin_users_sheet.find(str(user_id))
            if cell:
                row = self.spin_users_sheet.row_values(cell.row)

                if username is not None:
                    self.spin_users_sheet.update_cell(cell.row, 2, username)

                if available_spins is not None:
                    self.spin_users_sheet.update_cell(cell.row, 3, available_spins)

                if total_spins_used is not None:
                    self.spin_users_sheet.update_cell(cell.row, 4, total_spins_used)
                    self.spin_users_sheet.update_cell(cell.row, 8, self._get_timestamp())  # last_spin_at

                if total_chips_earned is not None:
                    self.spin_users_sheet.update_cell(cell.row, 5, total_chips_earned)

                if total_deposit is not None:
                    self.spin_users_sheet.update_cell(cell.row, 6, total_deposit)

                if pppoker_id is not None:
                    # Only update if column exists (for backward compatibility)
                    try:
                        self.spin_users_sheet.update_cell(cell.row, 9, pppoker_id)
                    except Exception as e:
                        print(f"Note: PPPoker ID column not yet added to sheet: {e}")

                return True
            return False
        except Exception as e:
            print(f"Error updating spin user: {e}")
            return False

    # Removed log_spin method - no longer needed (display prizes not tracked)

    def get_pppoker_id_from_deposits(self, user_id: int) -> str:
        """Get user's PPPoker ID from their last deposit"""
        try:
            deposits = self.deposits_sheet.get_all_records()

            # Filter deposits for this user (with proper string handling)
            user_deposits = [d for d in deposits
                           if str(d.get('User ID', '')).strip() == str(user_id).strip()]

            if user_deposits:
                # Get the most recent deposit (last in list)
                last_deposit = user_deposits[-1]

                # Try multiple possible column names
                pppoker_id = (last_deposit.get('PPPoker ID') or
                            last_deposit.get('PPPoker Id') or
                            last_deposit.get('Pppoker ID') or
                            last_deposit.get('pppoker_id') or
                            last_deposit.get('PPPoker Id'))

                if pppoker_id and str(pppoker_id).strip():
                    return str(pppoker_id).strip()

            return ''
        except Exception as e:
            print(f"Error getting PPPoker ID from deposits: {e}")
            return ''

    def log_milestone_reward(self, user_id: int, username: str, milestone_type: str,
                            milestone_count: int, chips_awarded: int, triggered_at: int, pppoker_id: str = ''):
        """Log a milestone reward"""
        try:
            # Try with PPPoker ID column first
            try:
                self.milestone_rewards_sheet.append_row([
                    user_id,
                    username,
                    milestone_type,
                    milestone_count,
                    chips_awarded,
                    triggered_at,
                    self._get_timestamp(),
                    'No',  # Approved (default: No)
                    '',    # Approved By (default: empty)
                    pppoker_id
                ])
            except Exception as col_error:
                # If that fails (column doesn't exist), try without PPPoker ID
                print(f"Note: Logging without PPPoker ID column (not yet added): {col_error}")
                self.milestone_rewards_sheet.append_row([
                    user_id,
                    username,
                    milestone_type,
                    milestone_count,
                    chips_awarded,
                    triggered_at,
                    self._get_timestamp(),
                    'No',  # Approved (default: No)
                    ''     # Approved By (default: empty)
                ])
            return True
        except Exception as e:
            print(f"Error logging milestone reward: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_pending_spin_rewards(self) -> List[Dict]:
        """Get all pending milestone/surprise rewards"""
        try:
            all_rows = self.milestone_rewards_sheet.get_all_values()[1:]  # Skip header
            pending = []

            for idx, row in enumerate(all_rows, start=2):  # Start from row 2 (row 1 is header)
                if len(row) >= 7:
                    try:
                        # Check if approved (column 7 = index 7 in 0-based)
                        approved = row[7] if len(row) > 7 else 'No'
                        approved_by = row[8] if len(row) > 8 else ''

                        # Only show pending (not approved)
                        if approved != 'Yes':
                            # Build prize name
                            milestone_type = row[2] if len(row) > 2 else 'unknown'
                            chips_awarded = row[4] if len(row) > 4 else '0'
                            pppoker_id = row[9] if len(row) > 9 else ''
                            prize_name = f"{chips_awarded} chips ({milestone_type})"

                            pending.append({
                                'spin_id': str(idx),  # Use row number as ID
                                'user_id': str(row[0]),
                                'username': str(row[1]) if len(row) > 1 else 'Unknown',
                                'prize': prize_name,
                                'chips': str(chips_awarded),
                                'date': str(row[6]) if len(row) > 6 else '',
                                'approved': False,
                                'approved_by': str(approved_by),
                                'pppoker_id': str(pppoker_id),
                                'row': idx
                            })
                    except Exception as e:
                        print(f"Error processing row {idx}: {e}")
                        continue

            return pending
        except Exception as e:
            print(f"Error getting pending spin rewards: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_spin_by_id(self, spin_id: str) -> Optional[Dict]:
        """Get milestone reward data by row ID"""
        try:
            row_num = int(spin_id)
            row = self.milestone_rewards_sheet.row_values(row_num)

            if row and len(row) >= 7:
                approved = row[7] if len(row) > 7 else 'No'
                approved_by = row[8] if len(row) > 8 else ''
                pppoker_id = row[9] if len(row) > 9 else ''
                prize_name = f"{row[4]} chips ({row[2]})"

                return {
                    'spin_id': spin_id,
                    'user_id': int(row[0]),
                    'username': row[1],
                    'prize': prize_name,
                    'chips': int(row[4]),
                    'milestone_type': row[2],
                    'date': row[6],
                    'approved': approved == 'Yes',
                    'approved_by': approved_by,
                    'pppoker_id': pppoker_id,
                    'row': row_num
                }
            return None
        except Exception as e:
            print(f"Error getting spin by ID: {e}")
            return None

    def approve_spin_reward(self, spin_id: str, admin_id: int, admin_name: str):
        """Approve a milestone/surprise reward"""
        try:
            row_num = int(spin_id)
            # Add "Yes" to column 8 (Approved) and admin name to column 9 (Approved By)
            self.milestone_rewards_sheet.update_cell(row_num, 8, 'Yes')
            self.milestone_rewards_sheet.update_cell(row_num, 9, f"{admin_name}")
            return True
        except Exception as e:
            print(f"Error approving spin reward: {e}")
            return False

    def get_spin_statistics(self) -> Dict:
        """Get overall spin statistics"""
        try:
            users = self.spin_users_sheet.get_all_values()[1:]  # Skip header
            rewards = self.milestone_rewards_sheet.get_all_values()[1:]  # Skip header

            total_users = len(users)
            total_spins_used = sum(int(row[3]) if len(row) > 3 and row[3] else 0 for row in users)
            total_chips_awarded = sum(int(row[4]) if len(row) > 4 and row[4] else 0 for row in users)

            pending_rewards = len([row for row in rewards if len(row) >= 8 and (row[7] if len(row) > 7 else 'No') == 'No'])
            approved_rewards = len([row for row in rewards if len(row) >= 8 and (row[7] if len(row) > 7 else 'No') == 'Yes'])

            # Top users by spins
            top_users = sorted(
                [{'username': row[1], 'total_spins': int(row[3]) if row[3] else 0} for row in users],
                key=lambda x: x['total_spins'],
                reverse=True
            )

            return {
                'total_users': total_users,
                'total_spins_used': total_spins_used,
                'total_chips_awarded': total_chips_awarded,
                'pending_rewards': pending_rewards,
                'approved_rewards': approved_rewards,
                'top_users': top_users
            }
        except Exception as e:
            print(f"Error getting spin statistics: {e}")
            return {
                'total_users': 0,
                'total_spins_used': 0,
                'total_chips_awarded': 0,
                'pending_rewards': 0,
                'approved_rewards': 0,
                'top_users': []
            }

