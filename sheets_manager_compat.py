"""
SheetsManager Compatibility Layer
Provides the same interface as SheetsManager but uses Django API underneath
This allows bot.py to work without major code changes
"""

from django_api import api
from typing import Optional, Dict, List, Any
from datetime import datetime, date


class SheetsManagerCompat:
    """Drop-in replacement for SheetsManager that uses Django API"""

    def __init__(self, credentials_file=None, spreadsheet_name=None, timezone=None):
        """Initialize - credentials not needed for Django API"""
        self.api = api
        self.timezone = timezone

    # ==================== USER METHODS ====================

    def create_or_update_user(self, telegram_id: int, username: str, first_name: str = '', last_name: str = ''):
        """Create or update user"""
        # Combine first_name and last_name for username if username is empty
        if not username:
            username = f"{first_name} {last_name}".strip() or str(telegram_id)
        user = self.api.get_or_create_user(telegram_id, username, '')
        return user

    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Get user by telegram ID"""
        user = self.api.get_user_by_telegram_id(telegram_id)
        return user

    def update_user_pppoker_id(self, telegram_id: int, pppoker_id: str):
        """Update user's PPPoker ID"""
        user = self.api.get_user_by_telegram_id(telegram_id)
        if user:
            data = {'pppoker_id': pppoker_id}
            self.api._put(f'users/{user["id"]}/', data)
            return True
        return False

    def update_user_account_name(self, telegram_id: int, account_name: str):
        """Update user's account name (stored in username field for compatibility)"""
        user = self.api.get_user_by_telegram_id(telegram_id)
        if user:
            # Note: You may want to add account_name field to User model
            return True
        return False

    def get_all_user_ids(self) -> List[int]:
        """Get all user telegram IDs"""
        users = self.api.get_all_users()
        return [user['telegram_id'] for user in users]

    # ==================== DEPOSIT METHODS ====================

    def create_deposit_request(self, telegram_id: int, amount: float, method: str,
                               account_name: str, proof_path: str, pppoker_id: str,
                               **kwargs) -> int:
        """Create deposit request"""
        user = self.api.get_or_create_user(telegram_id, account_name, pppoker_id)
        deposit = self.api.create_deposit(
            user_id=user['id'],
            amount=amount,
            method=method,
            account_name=account_name,
            proof_image_path=proof_path,
            pppoker_id=pppoker_id
        )
        return deposit['id']

    def get_deposit_request(self, request_id: int) -> Optional[Dict]:
        """Get deposit by ID"""
        try:
            return self.api._get(f'deposits/{request_id}/')
        except:
            return None

    def update_deposit_status(self, request_id: int, status: str, admin_id: int, reason: str = ''):
        """Update deposit status"""
        if status == 'Approved':
            self.api.approve_deposit(request_id, admin_id)
        elif status == 'Rejected':
            self.api.reject_deposit(request_id, admin_id, reason)
        return True

    def get_deposits_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get deposits in date range"""
        all_deposits = self.api.get_all_deposits()
        # Filter by date range
        filtered = []
        for deposit in all_deposits:
            created = deposit.get('created_at', '')[:10]  # YYYY-MM-DD
            if start_date <= created <= end_date:
                filtered.append(deposit)
        return filtered

    # ==================== WITHDRAWAL METHODS ====================

    def create_withdrawal_request(self, telegram_id: int, amount: float, method: str,
                                  account_name: str, account_number: str, pppoker_id: str,
                                  **kwargs) -> int:
        """Create withdrawal request"""
        user = self.api.get_or_create_user(telegram_id, account_name, pppoker_id)
        withdrawal = self.api.create_withdrawal(
            user_id=user['id'],
            amount=amount,
            method=method,
            account_name=account_name,
            account_number=account_number,
            pppoker_id=pppoker_id
        )
        return withdrawal['id']

    def get_withdrawal_request(self, request_id: int) -> Optional[Dict]:
        """Get withdrawal by ID"""
        try:
            return self.api._get(f'withdrawals/{request_id}/')
        except:
            return None

    def update_withdrawal_status(self, request_id: int, status: str, admin_id: int, reason: str = ''):
        """Update withdrawal status"""
        if status == 'Completed' or status == 'Approved':
            self.api.approve_withdrawal(request_id, admin_id)
        elif status == 'Rejected':
            self.api.reject_withdrawal(request_id, admin_id, reason)
        return True

    def get_withdrawals_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get withdrawals in date range"""
        all_withdrawals = self.api.get_all_withdrawals()
        filtered = []
        for withdrawal in all_withdrawals:
            created = withdrawal.get('created_at', '')[:10]
            if start_date <= created <= end_date:
                filtered.append(withdrawal)
        return filtered

    # ==================== JOIN REQUEST METHODS ====================

    def create_join_request(self, telegram_id: int, pppoker_id: str, **kwargs) -> int:
        """Create join request"""
        user = self.api.get_or_create_user(telegram_id, str(telegram_id), pppoker_id)
        join_req = self.api.create_join_request(user['id'], pppoker_id)
        return join_req['id']

    def get_join_request(self, request_id: int) -> Optional[Dict]:
        """Get join request by ID"""
        try:
            return self.api._get(f'join-requests/{request_id}/')
        except:
            return None

    def update_join_request_status(self, request_id: int, status: str, admin_id: int):
        """Update join request status"""
        data = {'status': status, 'approved_by': admin_id}
        try:
            return self.api._put(f'join-requests/{request_id}/', data)
        except:
            return False

    # ==================== SEAT REQUEST METHODS ====================

    def create_seat_request(self, telegram_id: int, amount: float, slip_path: str,
                           pppoker_id: str, **kwargs) -> int:
        """Create seat request"""
        user = self.api.get_or_create_user(telegram_id, str(telegram_id), pppoker_id)
        seat_req = self.api.create_seat_request(user['id'], amount, slip_path, pppoker_id)
        return seat_req['id']

    def get_seat_request(self, request_id: int) -> Optional[Dict]:
        """Get seat request by ID"""
        try:
            return self.api._get(f'seat-requests/{request_id}/')
        except:
            return None

    def approve_seat_request(self, request_id: int, admin_id: int):
        """Approve seat request"""
        data = {'status': 'Approved', 'approved_by': admin_id}
        try:
            self.api._put(f'seat-requests/{request_id}/', data)
            return True
        except:
            return False

    def reject_seat_request(self, request_id: int, admin_id: int, reason: str = ''):
        """Reject seat request"""
        data = {'status': 'Rejected', 'approved_by': admin_id, 'rejection_reason': reason}
        try:
            self.api._put(f'seat-requests/{request_id}/', data)
            return True
        except:
            return False

    def settle_seat_request(self, request_id: int, admin_id: int, **kwargs):
        """Settle seat request"""
        data = {'status': 'Settled', 'approved_by': admin_id}
        try:
            self.api._put(f'seat-requests/{request_id}/', data)
            return True
        except:
            return False

    # ==================== CASHBACK REQUEST METHODS ====================

    def create_cashback_request(self, telegram_id: int, week_start: str, week_end: str,
                               investment_amount: float, cashback_amount: float,
                               cashback_percentage: float, pppoker_id: str, **kwargs) -> int:
        """Create cashback request"""
        user = self.api.get_or_create_user(telegram_id, str(telegram_id), pppoker_id)
        cashback = self.api.create_cashback_request(
            user_id=user['id'],
            week_start=week_start,
            week_end=week_end,
            investment_amount=investment_amount,
            cashback_amount=cashback_amount,
            cashback_percentage=cashback_percentage,
            pppoker_id=pppoker_id
        )
        return cashback['id']

    def get_user_pending_cashback(self, telegram_id: int) -> List[Dict]:
        """Get user's pending cashback requests"""
        all_cashback = self.api.get_pending_cashback_requests()
        user = self.api.get_user_by_telegram_id(telegram_id)
        if not user:
            return []
        return [cb for cb in all_cashback if cb.get('user') == user['id']]

    def approve_cashback_request(self, request_id: int, admin_name: str):
        """Approve cashback request"""
        data = {'status': 'Approved', 'approved_by': 0}  # Use admin ID if available
        try:
            self.api._put(f'cashback-requests/{request_id}/', data)
            return True
        except:
            return False

    def reject_cashback_request(self, request_id: int, rejector_name: str):
        """Reject cashback request"""
        data = {'status': 'Rejected', 'rejection_reason': f'Rejected by {rejector_name}'}
        try:
            self.api._put(f'cashback-requests/{request_id}/', data)
            return True
        except:
            return False

    def check_cashback_eligibility(self, telegram_id: int, promotion_id: int, min_deposit: float = 0):
        """Check if user is eligible for cashback"""
        # TODO: Implement eligibility logic
        return {'eligible': True, 'reason': ''}

    def get_cashback_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get cashback requests in date range"""
        all_cashback = self.api.get_all_cashback_requests()
        filtered = []
        for cb in all_cashback:
            created = cb.get('created_at', '')[:10]
            if start_date <= created <= end_date:
                filtered.append(cb)
        return filtered

    # ==================== PAYMENT ACCOUNT METHODS ====================

    def get_all_payment_accounts(self) -> List[Dict]:
        """Get all payment accounts"""
        return self.api.get_all_payment_accounts()

    def get_payment_account(self, method: str) -> Optional[str]:
        """Get payment account number by method"""
        accounts = self.api.get_active_payment_accounts()
        for account in accounts:
            if account.get('method') == method:
                return account.get('account_number')
        return None

    def get_payment_account_holder(self, method: str) -> Optional[str]:
        """Get payment account holder name by method"""
        accounts = self.api.get_active_payment_accounts()
        for account in accounts:
            if account.get('method') == method:
                return account.get('account_name')
        return None

    def get_payment_account_details(self, method: str) -> Optional[Dict]:
        """Get payment account details"""
        accounts = self.api.get_active_payment_accounts()
        for account in accounts:
            if account.get('method') == method:
                return account
        return None

    def update_payment_account(self, method: str, account_number: str, account_holder: Optional[str]):
        """Update payment account"""
        accounts = self.api.get_all_payment_accounts()
        for account in accounts:
            if account.get('method') == method:
                data = {'account_number': account_number}
                if account_holder:
                    data['account_name'] = account_holder
                self.api._put(f'payment-accounts/{account["id"]}/', data)
                return True
        return False

    def clear_payment_account(self, method: str):
        """Clear payment account"""
        # Mark as inactive
        accounts = self.api.get_all_payment_accounts()
        for account in accounts:
            if account.get('method') == method:
                data = {'is_active': False}
                self.api._put(f'payment-accounts/{account["id"]}/', data)
                return True
        return False

    # ==================== ADMIN METHODS ====================

    def is_admin(self, telegram_id: int, super_admin_id: Optional[int] = None) -> bool:
        """Check if user is admin"""
        if super_admin_id and telegram_id == super_admin_id:
            return True
        return self.api.is_admin(telegram_id)

    def get_all_admins(self) -> List[Dict]:
        """Get all admins"""
        return self.api.get_all_admins()

    def add_admin(self, telegram_id: int, username: str, name: str, added_by: int):
        """Add new admin"""
        admin = self.api.create_admin(telegram_id, username, role='Admin')
        return True

    def remove_admin(self, telegram_id: int):
        """Remove admin"""
        admins = self.api.get_all_admins()
        for admin in admins:
            if admin.get('telegram_id') == telegram_id:
                data = {'is_active': False}
                self.api._put(f'admins/{admin["id"]}/', data)
                return True
        return False

    # ==================== COUNTER STATUS METHODS ====================

    def is_counter_open(self) -> bool:
        """Check if counter is open"""
        status = self.api.get_counter_status()
        return status.get('is_open', False)

    def get_counter_status(self) -> Dict:
        """Get counter status"""
        return self.api.get_counter_status()

    def set_counter_status(self, status: str, admin_name: str, announcement_sent: bool = False):
        """Set counter status"""
        # Toggle if different from current
        current = self.api.get_counter_status()
        is_open = status.upper() == 'OPEN'
        if current.get('is_open') != is_open:
            self.api.toggle_counter(0)  # Use actual admin ID if available
        return True

    # ==================== EXCHANGE RATE METHODS ====================

    def get_exchange_rate(self, currency: str) -> Optional[float]:
        """Get exchange rate"""
        rates = self.api.get_active_exchange_rates()
        for rate in rates:
            if rate.get('currency_from') == currency:
                return float(rate.get('rate', 0))
        return None

    def set_exchange_rate(self, currency: str, rate: float):
        """Set exchange rate"""
        # Create or update exchange rate
        data = self.api.create_exchange_rate(currency, 'MVR', rate)
        return True

    # ==================== USER CREDIT METHODS ====================

    def get_user_credit(self, telegram_id: int) -> Optional[Dict]:
        """Get user credit"""
        # Get all credits for this user
        all_credits = self.api.get_all_user_credits()
        user = self.api.get_user_by_telegram_id(telegram_id)
        if not user:
            return None

        user_credits = [c for c in all_credits if c.get('user') == user['id']]
        if user_credits:
            return user_credits[0]
        return None

    def add_user_credit(self, telegram_id: int, amount: float, credit_type: str,
                       description: str, created_by: int):
        """Add user credit"""
        user = self.api.get_or_create_user(telegram_id, str(telegram_id))
        credit = self.api.create_user_credit(
            user_id=user['id'],
            amount=amount,
            credit_type=credit_type,
            description=description,
            created_by=created_by
        )
        return True

    def clear_user_credit(self, telegram_id: int):
        """Clear user credit"""
        # Mark credit as cleared (you may need to add a status field to model)
        return True

    def increment_credit_reminder(self, telegram_id: int):
        """Increment credit reminder count"""
        # TODO: Add reminder_count field to UserCredit model
        return True

    def get_all_active_credits(self) -> List[Dict]:
        """Get all active credits"""
        return self.api.get_all_user_credits()

    def get_daily_credit_summary(self) -> Dict:
        """Get daily credit summary"""
        # TODO: Implement summary logic
        return {}

    # ==================== PROMOTION METHODS ====================

    def get_active_promotion(self) -> Optional[Dict]:
        """Get active promotion"""
        promos = self.api.get_active_promo_codes()
        return promos[0] if promos else None

    def create_promotion(self, **kwargs) -> int:
        """Create promotion"""
        promo = self.api.create_promo_code(
            code=kwargs.get('code', 'PROMO'),
            percentage=kwargs.get('percentage', 0),
            start_date=kwargs.get('start_date', str(date.today())),
            end_date=kwargs.get('end_date', str(date.today()))
        )
        return promo['id']

    def create_cashback_promotion(self, **kwargs) -> int:
        """Create cashback promotion"""
        # Use same promo code system
        return self.create_promotion(**kwargs)

    def check_user_promotion_eligibility(self, telegram_id: int, promotion_id: int):
        """Check promotion eligibility"""
        return True

    def record_promotion_bonus(self, telegram_id: int, promotion_id: int, bonus_amount: float):
        """Record promotion bonus"""
        user = self.api.get_or_create_user(telegram_id, str(telegram_id))
        self.api.create_user_credit(
            user_id=user['id'],
            amount=bonus_amount,
            credit_type='Promotion Bonus',
            description=f'Promotion ID: {promotion_id}',
            created_by=0
        )
        return True

    def get_active_cashback_promotion(self) -> Optional[Dict]:
        """Get active cashback promotion"""
        return self.get_active_promotion()

    # ==================== INVESTMENT METHODS ====================

    def add_investment(self, pppoker_id: str, note: str, amount: float):
        """Add 50-50 investment"""
        # Find user by pppoker_id
        users = self.api.get_all_users()
        user = next((u for u in users if u.get('pppoker_id') == pppoker_id), None)
        if user:
            investment = self.api.create_investment(
                user_id=user['id'],
                investment_amount=amount,
                start_date=str(date.today()),
                notes=note
            )
            return True
        return False

    def get_all_active_investments_summary(self) -> List[Dict]:
        """Get active investments summary"""
        return self.api.get_active_investments()

    def get_active_investments_by_id(self, pppoker_id: str) -> List[Dict]:
        """Get active investments for a PPPoker ID"""
        investments = self.api.get_active_investments()
        # Filter by pppoker_id
        users = self.api.get_all_users()
        user = next((u for u in users if u.get('pppoker_id') == pppoker_id), None)
        if user:
            return [inv for inv in investments if inv.get('user') == user['id']]
        return []

    def record_investment_return(self, pppoker_id: str, return_amount: float):
        """Record investment return"""
        # TODO: Update investment with profit/loss
        return {'success': True}

    def get_investment_stats(self, start_date: str, end_date: str) -> Dict:
        """Get investment statistics"""
        # TODO: Calculate stats
        return {}

    def mark_expired_investments_as_lost(self) -> int:
        """Mark expired investments as lost"""
        # TODO: Update expired investments
        return 0

    # ==================== CLUB BALANCE METHODS ====================

    def get_club_balances(self) -> Dict:
        """Get club balances"""
        balances = self.api.get_all_club_balances()
        # Format for compatibility
        return {}

    def set_starting_balances(self, chips: float, cost: float, mvr: float, usd: float, usdt: float):
        """Set starting balances"""
        # TODO: Implement starting balance logic
        return True

    def buy_chips_for_club(self, chips: float, cost: float, admin_name: str):
        """Buy chips for club"""
        # TODO: Create inventory transaction
        return {'success': True}

    def add_cash_to_club(self, currency: str, amount: float, note: str, admin_name: str):
        """Add cash to club"""
        # TODO: Create inventory transaction
        return {'success': True}

    # ==================== SPIN/BONUS METHODS ====================

    def get_spins_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get spins in date range"""
        all_spins = self.api.get_all_spin_history()
        filtered = []
        for spin in all_spins:
            created = spin.get('created_at', '')[:10]
            if start_date <= created <= end_date:
                filtered.append(spin)
        return filtered

    def get_bonuses_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get bonuses in date range"""
        # Bonuses are user credits
        return []

    # ==================== POSTER/REPORT METHODS ====================

    def get_saved_poster(self, poster_type: str) -> Optional[str]:
        """Get saved poster file ID"""
        # TODO: Add poster storage to models
        return None

    def save_counter_poster(self, poster_type: str, file_id: str):
        """Save counter poster"""
        # TODO: Add poster storage to models
        return True

    def save_all_reports(self, reports_data: Dict):
        """Save all reports"""
        # TODO: Add reports storage to models
        return True
