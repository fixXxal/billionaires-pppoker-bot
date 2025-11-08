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
            self.payment_accounts_sheet.append_row(['USDT', os.getenv('USDT_WALLET', ''), '', self._get_timestamp()])

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
        except gspread.CellNotFound:
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
        except gspread.CellNotFound:
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
        except gspread.CellNotFound:
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
        except gspread.CellNotFound:
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
        except gspread.CellNotFound:
            pass
        return None

    def get_payment_account_holder(self, method: str) -> Optional[str]:
        """Get payment account holder name for a specific method"""
        try:
            cell = self.payment_accounts_sheet.find(method)
            if cell:
                row_data = self.payment_accounts_sheet.row_values(cell.row)
                return row_data[2] if len(row_data) > 2 else None
        except gspread.CellNotFound:
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
        except gspread.CellNotFound:
            pass
        return None

    def update_payment_account(self, method: str, account_number: str, account_holder: str = None):
        """Update payment account number and holder name"""
        try:
            cell = self.payment_accounts_sheet.find(method)
            if cell:
                row = cell.row
                self.payment_accounts_sheet.update_cell(row, 2, account_number)
                if account_holder:
                    self.payment_accounts_sheet.update_cell(row, 3, account_holder)
                self.payment_accounts_sheet.update_cell(row, 4, self._get_timestamp())
            else:
                # Add new payment method
                self.payment_accounts_sheet.append_row([method, account_number, account_holder or '', self._get_timestamp()])
        except gspread.CellNotFound:
            # Add new payment method
            self.payment_accounts_sheet.append_row([method, account_number, account_holder or '', self._get_timestamp()])

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
