"""
Django API Wrapper for Telegram Bot
Provides simple interface to interact with Django REST API
Replaces direct Google Sheets access with fast database queries
"""

import os
import logging
import requests
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Get Django API URL from environment or use default
DJANGO_API_URL = os.getenv('DJANGO_API_URL', 'http://localhost:8000/api')


class DjangoAPI:
    """Wrapper class for Django REST API endpoints"""

    def __init__(self, base_url: str = DJANGO_API_URL):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make GET request to API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"GET {url} failed: {e}, Response: {response.text if 'response' in locals() else 'N/A'}")
            raise

    def _post(self, endpoint: str, data: Optional[Dict] = None) -> Any:
        """Make POST request to API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"POST {url} failed: {e}, Response: {response.text if 'response' in locals() else 'N/A'}")
            raise

    def _put(self, endpoint: str, data: Optional[Dict] = None) -> Any:
        """Make PUT request to API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.put(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"PUT {url} failed: {e}, Response: {response.text if 'response' in locals() else 'N/A'}")
            raise

    def _patch(self, endpoint: str, data: Optional[Dict] = None) -> Any:
        """Make PATCH request to API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.patch(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"PATCH {url} failed: {e}, Response: {response.text if 'response' in locals() else 'N/A'}")
            raise

    def _delete(self, endpoint: str) -> Any:
        """Make DELETE request to API"""
        url = f"{self.base_url}/{endpoint}"
        response = self.session.delete(url, timeout=10)
        response.raise_for_status()
        return response.json() if response.text else {}

    # ==================== USER METHODS ====================

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Get user by Telegram ID"""
        try:
            return self._get(f'users/by_telegram_id/', params={'telegram_id': telegram_id})
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def create_user(self, telegram_id: int, username: str, pppoker_id: str = '') -> Dict:
        """Create or get user by Telegram ID"""
        data = {
            'telegram_id': telegram_id,
            'username': username,
            'pppoker_id': pppoker_id
        }
        result = self._post('users/by_telegram_id/', data)
        return result.get('user')

    def get_or_create_user(self, telegram_id: int, username: str, pppoker_id: str = '') -> Dict:
        """Get existing user or create new one"""
        return self.create_user(telegram_id, username, pppoker_id)

    def create_or_update_user(self, telegram_id: int, username: str = None,
                             first_name: str = None, last_name: str = None,
                             pppoker_id: str = '') -> Dict:
        """Create or update user with additional fields"""
        # Construct username from first_name and last_name if not provided
        if not username:
            username = f"{first_name or ''}{last_name or ''}".strip() or f"user_{telegram_id}"
        return self.create_user(telegram_id, username, pppoker_id)

    def update_user_balance(self, user_id: int, new_balance: float) -> Dict:
        """Update user's balance"""
        data = {'balance': new_balance}
        return self._put(f'users/{user_id}/', data)

    def get_all_users(self) -> List[Dict]:
        """Get all users"""
        return self._get('users/')

    # ==================== DEPOSIT METHODS ====================

    def create_deposit(self, user_id: int, amount: float, method: str, account_name: str,
                      proof_image_path: str, pppoker_id: str) -> Dict:
        """Create new deposit request"""
        data = {
            'user': user_id,
            'amount': amount,
            'method': method,
            'account_name': account_name,
            'proof_image_path': proof_image_path,
            'pppoker_id': pppoker_id,
            'status': 'Pending'
        }
        return self._post('deposits/', data)

    def get_pending_deposits(self) -> List[Dict]:
        """Get all pending deposits"""
        return self._get('deposits/pending/')

    def approve_deposit(self, deposit_id: int, admin_id: int) -> Dict:
        """Approve a deposit"""
        data = {'admin_id': admin_id}
        return self._post(f'deposits/{deposit_id}/approve/', data)

    def reject_deposit(self, deposit_id: int, admin_id: int, reason: str = '') -> Dict:
        """Reject a deposit"""
        data = {'admin_id': admin_id, 'reason': reason}
        return self._post(f'deposits/{deposit_id}/reject/', data)

    def get_all_deposits(self) -> List[Dict]:
        """Get all deposits"""
        return self._get('deposits/')

    def get_user_deposits(self, telegram_id: int) -> List[Dict]:
        """Get all deposits for a specific user"""
        response = self._get(f'deposits/?user={telegram_id}')
        # Handle paginated response
        if isinstance(response, dict) and 'results' in response:
            return response['results']
        return response

    # ==================== WITHDRAWAL METHODS ====================

    def create_withdrawal(self, user_id: int, amount: float, method: str,
                         account_name: str, account_number: str, pppoker_id: str) -> Dict:
        """Create new withdrawal request"""
        data = {
            'user': user_id,
            'amount': amount,
            'method': method,
            'account_name': account_name,
            'account_number': account_number,
            'pppoker_id': pppoker_id,
            'status': 'Pending'
        }
        return self._post('withdrawals/', data)

    def get_pending_withdrawals(self) -> List[Dict]:
        """Get all pending withdrawals"""
        return self._get('withdrawals/pending/')

    def approve_withdrawal(self, withdrawal_id: int, admin_id: int) -> Dict:
        """Approve a withdrawal"""
        data = {'admin_id': admin_id}
        return self._post(f'withdrawals/{withdrawal_id}/approve/', data)

    def reject_withdrawal(self, withdrawal_id: int, admin_id: int, reason: str = '') -> Dict:
        """Reject a withdrawal"""
        data = {'admin_id': admin_id, 'reason': reason}
        return self._post(f'withdrawals/{withdrawal_id}/reject/', data)

    def get_all_withdrawals(self) -> List[Dict]:
        """Get all withdrawals"""
        return self._get('withdrawals/')

    # ==================== SPIN USER METHODS ====================

    def get_or_create_spin_user(self, telegram_id: int) -> Dict:
        """Get or create spin user by Telegram ID"""
        data = {'telegram_id': telegram_id}
        result = self._post('spin-users/by_telegram_id/', data)
        return result.get('spin_user')

    def add_spins(self, spin_user_id: int, spins: int) -> Dict:
        """Add spins to user"""
        data = {'spins': spins}
        return self._post(f'spin-users/{spin_user_id}/add_spins/', data)

    def get_spin_user(self, telegram_id: int) -> Optional[Dict]:
        """Get spin user by telegram ID (returns None if not exists)"""
        try:
            result = self._get(f'spin-users/by_telegram_id/', params={'telegram_id': telegram_id})
            return result.get('spin_user')
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def create_spin_user(self, user_id: int, username: str, available_spins: int = 0,
                        total_deposit: float = 0, pppoker_id: str = '') -> Dict:
        """Create new spin user (or get existing) and set initial values"""
        # First ensure the main user exists
        self.get_or_create_user(user_id, username, pppoker_id)

        # Get or create spin user
        result = self._post('spin-users/by_telegram_id/', {'telegram_id': user_id})
        spin_user = result.get('spin_user')

        # Update with provided values using PUT
        spin_user_id = spin_user.get('id')
        updated_data = {
            'available_spins': available_spins,
            'total_deposit': total_deposit,
            'total_spins_used': spin_user.get('total_spins_used', 0),
            'total_chips_earned': spin_user.get('total_chips_earned', 0)
        }
        return self._put(f'spin-users/{spin_user_id}/', updated_data)

    def update_spin_user(self, user_id: int, username: str = None, available_spins: int = None,
                        total_deposit: float = None, pppoker_id: str = None,
                        total_chips_earned: int = None, total_spins_used: int = None) -> Dict:
        """Update existing spin user"""
        # Get the spin user first
        result = self._post('spin-users/by_telegram_id/', {'telegram_id': user_id})
        spin_user = result.get('spin_user')
        spin_user_id = spin_user.get('id')

        # Update main user's pppoker_id if provided
        if pppoker_id is not None:
            try:
                user = self.get_user_by_telegram_id(user_id)
                if user and user.get('pppoker_id') != pppoker_id:
                    # Update main user's pppoker_id
                    self.get_or_create_user(user_id, username or user.get('username'), pppoker_id)
            except Exception as e:
                logger.warning(f"Could not update pppoker_id for user {user_id}: {e}")

        # Build update data with only provided fields
        update_data = {
            'available_spins': available_spins if available_spins is not None else spin_user.get('available_spins', 0),
            'total_deposit': total_deposit if total_deposit is not None else spin_user.get('total_deposit', 0),
            'total_spins_used': total_spins_used if total_spins_used is not None else spin_user.get('total_spins_used', 0),
            'total_chips_earned': total_chips_earned if total_chips_earned is not None else spin_user.get('total_chips_earned', 0)
        }

        return self._put(f'spin-users/{spin_user_id}/', update_data)

    # ==================== SPIN HISTORY METHODS ====================

    def process_spin(self, telegram_id: int, results: List[Dict]) -> Dict:
        """Process one or more spins"""
        data = {
            'telegram_id': telegram_id,
            'spin_count': len(results),
            'results': results
        }
        return self._post('spin-history/process_spin/', data)

    def get_pending_spin_rewards(self) -> List[Dict]:
        """Get all pending spin rewards"""
        return self._get('spin-history/pending/')

    def approve_spin_reward(self, spin_id: int, admin_id: int) -> Dict:
        """Approve a spin reward"""
        data = {'admin_id': admin_id}
        return self._post(f'spin-history/{spin_id}/approve/', data)

    def get_all_spin_history(self) -> List[Dict]:
        """Get all spin history"""
        return self._get('spin-history/')

    def get_spin_statistics(self) -> Dict:
        """Get spin bot statistics (total users, spins, chips, etc.)"""
        return self._get('spin-users/statistics/')

    # ==================== JOIN REQUEST METHODS ====================

    def create_join_request(self, user_id: int, pppoker_id: str) -> Dict:
        """Create new join request"""
        data = {
            'user': user_id,
            'pppoker_id': pppoker_id,
            'status': 'Pending'
        }
        return self._post('join-requests/', data)

    def get_pending_join_requests(self) -> List[Dict]:
        """Get all pending join requests"""
        return self._get('join-requests/pending/')

    def get_all_join_requests(self) -> List[Dict]:
        """Get all join requests"""
        return self._get('join-requests/')

    # ==================== SEAT REQUEST METHODS ====================

    def create_seat_request(self, user_id: int, amount: float, slip_image_path: str, pppoker_id: str) -> Dict:
        """Create new seat request"""
        data = {
            'user': user_id,
            'amount': amount,
            'slip_image_path': slip_image_path,
            'pppoker_id': pppoker_id,
            'status': 'Pending'
        }
        return self._post('seat-requests/', data)

    def get_pending_seat_requests(self) -> List[Dict]:
        """Get all pending seat requests"""
        return self._get('seat-requests/pending/')

    def get_all_seat_requests(self) -> List[Dict]:
        """Get all seat requests"""
        return self._get('seat-requests/')

    def approve_seat_request(self, seat_request_id: int, admin_id: int) -> Dict:
        """Approve a seat request"""
        data = {'admin_id': admin_id}
        return self._post(f'seat-requests/{seat_request_id}/approve/', data)

    def reject_seat_request(self, seat_request_id: int, admin_id: int, reason: str = '') -> Dict:
        """Reject a seat request"""
        data = {'admin_id': admin_id, 'reason': reason}
        return self._post(f'seat-requests/{seat_request_id}/reject/', data)

    def settle_seat_request(self, seat_request_id: int, admin_id: int, payment_method: str = 'Seat Payment') -> Dict:
        """Settle a seat request - creates deposit and marks as completed"""
        data = {'admin_id': admin_id, 'payment_method': payment_method}
        return self._post(f'seat-requests/{seat_request_id}/settle/', data)

    def update_seat_request_slip_details(self, seat_request_id: int, sender_account_name: str, payment_method: str = '') -> Dict:
        """Update seat request with slip details (sender name, payment method)"""
        data = {'sender_account_name': sender_account_name, 'payment_method': payment_method}
        return self._patch(f'seat-requests/{seat_request_id}/', data)

    # ==================== CASHBACK REQUEST METHODS ====================

    def create_cashback_request(self, user_id: int = None, username: str = None,
                               pppoker_id: str = None, loss_amount: float = None,
                               cashback_amount: float = None, cashback_percentage: float = None,
                               promotion_id: int = None, week_start: str = None,
                               week_end: str = None, investment_amount: float = None,
                               telegram_id: int = None) -> Dict:
        """
        Create new cashback request

        Cashback is based on cumulative loss (500+ MVR), not weekly periods.
        week_start/week_end are legacy fields - we use today's date as placeholder.
        """
        from datetime import datetime

        # Get user database ID from telegram_id if provided
        if telegram_id and not user_id:
            user_obj = self.get_or_create_user(telegram_id, username or str(telegram_id))
            user_id = user_obj.get('id')
        elif user_id and not telegram_id:
            # Assume user_id is telegram_id in old format
            user_obj = self.get_or_create_user(user_id, username or str(user_id))
            user_id = user_obj.get('id')

        # Use today's date for legacy week fields (not actually weekly-based)
        if not week_start or not week_end:
            today = datetime.now().date().isoformat()
            week_start = today
            week_end = today

        # Use loss_amount as investment_amount if provided
        if loss_amount and not investment_amount:
            investment_amount = loss_amount

        data = {
            'user': user_id,
            'week_start': week_start,
            'week_end': week_end,
            'investment_amount': investment_amount or 0,
            'cashback_amount': cashback_amount or 0,
            'cashback_percentage': cashback_percentage or 0,
            'pppoker_id': pppoker_id or 'N/A',
            'status': 'Pending'
        }
        return self._post('cashback-requests/', data)

    def get_pending_cashback_requests(self) -> List[Dict]:
        """Get all pending cashback requests"""
        return self._get('cashback-requests/pending/')

    def get_all_cashback_requests(self) -> List[Dict]:
        """Get all cashback requests"""
        return self._get('cashback-requests/')

    def check_cashback_eligibility(self, telegram_id: int, promotion_id: int = None,
                                   min_deposit: float = 500) -> Dict:
        """Check if user is eligible for cashback based on loss and minimum deposit"""
        try:
            params = {
                'telegram_id': telegram_id,
                'min_deposit': min_deposit
            }
            if promotion_id:
                params['promotion_id'] = promotion_id

            result = self._get('cashback-requests/check_eligibility/', params=params)
            return result
        except Exception as e:
            logger.error(f"Error checking cashback eligibility: {e}")
            return {
                'eligible': False,
                'current_deposits': 0,
                'current_withdrawals': 0,
                'total_spin_rewards': 0,
                'total_bonuses': 0,
                'total_cashback': 0,
                'club_profit': 0,
                'user_loss': 0,
                'effective_new_deposits': 0,
                'last_claim_deposits': 0,
                'baseline': 0,
                'min_required': min_deposit,
                'deposits_exceed_withdrawals': False,
                'already_claimed': False
            }

    def record_cashback_bonus(self, telegram_id: int, promotion_id: int,
                             cashback_request_id: int, loss_amount: float,
                             cashback_amount: float) -> bool:
        """Record that a user received a cashback bonus"""
        try:
            # Get user's database ID
            user = self.get_or_create_user(telegram_id, str(telegram_id))
            user_id = user.get('id')

            data = {
                'user': user_id,
                'promotion': promotion_id,
                'cashback_request': cashback_request_id,
                'loss_amount': loss_amount,
                'cashback_amount': cashback_amount,
                'notes': f'Cashback bonus applied: {cashback_amount}'
            }
            self._post('cashback-eligibility/', data)
            return True
        except Exception as e:
            logger.error(f"Error recording cashback bonus: {e}")
            return False

    # ==================== PAYMENT ACCOUNT METHODS ====================

    def get_active_payment_accounts(self) -> List[Dict]:
        """Get all active payment accounts"""
        return self._get('payment-accounts/active/')

    def create_payment_account(self, method: str, account_name: str, account_number: str) -> Dict:
        """Create new payment account"""
        data = {
            'method': method,
            'account_name': account_name,
            'account_number': account_number,
            'is_active': True
        }
        return self._post('payment-accounts/', data)

    def update_payment_account(self, method: str, account_number: str, account_name: str = None) -> Dict:
        """Update or create payment account"""
        # First, try to get existing account by method
        try:
            accounts = self.get_all_payment_accounts()
            logger.info(f"Retrieved accounts: {accounts}, type: {type(accounts)}")

            # Handle case where accounts might be a string or error
            if not isinstance(accounts, list):
                logger.error(f"Expected list of accounts, got {type(accounts)}: {accounts}")
                accounts = []

            existing = next((acc for acc in accounts if isinstance(acc, dict) and acc.get('method') == method), None)

            data = {
                'method': method,
                'account_name': account_name or method,
                'account_number': account_number,
                'is_active': True
            }

            if existing:
                # Update existing account
                account_id = existing.get('id')
                logger.info(f"Updating existing payment account {method} (ID: {account_id})")
                return self._put(f'payment-accounts/{account_id}/', data)
            else:
                # Create new account
                logger.info(f"Creating new payment account {method}")
                return self._post('payment-accounts/', data)
        except Exception as e:
            logger.error(f"Error updating payment account {method}: {e}", exc_info=True)
            raise  # Re-raise so bot can show error to admin

    def get_all_payment_accounts(self) -> List[Dict]:
        """Get all payment accounts"""
        return self._get('payment-accounts/')

    # ==================== ADMIN METHODS ====================

    def is_admin(self, telegram_id: int) -> bool:
        """Check if telegram_id is an admin"""
        result = self._get('admins/check/', params={'telegram_id': telegram_id})
        return result.get('is_admin', False)

    def create_admin(self, telegram_id: int, username: str, role: str = 'Admin') -> Dict:
        """Create new admin"""
        data = {
            'telegram_id': telegram_id,
            'username': username,
            'role': role,
            'is_active': True
        }
        return self._post('admins/', data)

    def get_all_admins(self) -> List[Dict]:
        """Get all admins"""
        return self._get('admins/')

    # ==================== COUNTER STATUS METHODS ====================

    def get_counter_status(self) -> Dict:
        """Get current counter status"""
        return self._get('counter-status/current/')

    def toggle_counter(self, admin_id: int) -> Dict:
        """Toggle counter open/close"""
        data = {'admin_id': admin_id}
        return self._post('counter-status/toggle/', data)

    def is_counter_open(self) -> bool:
        """Check if counter is currently open"""
        try:
            status = self.get_counter_status()
            return status.get('is_open', True)
        except Exception:
            # If API fails, assume counter is open
            return True

    # ==================== PROMO CODE METHODS ====================

    def get_active_promo_codes(self, promo_type: str = None) -> List[Dict]:
        """Get all active promo codes, optionally filtered by type"""
        params = {}
        if promo_type:
            params['promo_type'] = promo_type
        return self._get('promo-codes/active/', params=params)

    def create_promo_code(self, code: str, percentage: float, start_date: str, end_date: str,
                         promo_type: str = 'bonus') -> Dict:
        """Create new promo code"""
        data = {
            'code': code,
            'percentage': percentage,
            'promo_type': promo_type,
            'start_date': start_date,
            'end_date': end_date,
            'is_active': True
        }
        return self._post('promo-codes/', data)

    def get_all_promo_codes(self) -> List[Dict]:
        """Get all promo codes"""
        return self._get('promo-codes/')

    def deactivate_promotion(self, promotion_id: int) -> bool:
        """Deactivate a promotion by setting is_active to False"""
        try:
            self._patch(f'promo-codes/{promotion_id}/', {'is_active': False})
            return True
        except Exception as e:
            logger.error(f"Error deactivating promotion {promotion_id}: {e}")
            return False

    def deactivate_cashback_promotion(self, promotion_id: int) -> bool:
        """Deactivate a cashback promotion by setting is_active to False"""
        try:
            self._patch(f'promo-codes/{promotion_id}/', {'is_active': False})
            return True
        except Exception as e:
            logger.error(f"Error deactivating cashback promotion {promotion_id}: {e}")
            return False

    def check_user_promotion_eligibility(self, telegram_id: int, promotion_id: int) -> bool:
        """Check if user is eligible for a promotion"""
        try:
            result = self._get('promotion-eligibility/check_eligibility/', params={
                'telegram_id': telegram_id,
                'promotion_id': promotion_id
            })
            return result.get('eligible', False)
        except Exception as e:
            logger.error(f"Error checking promotion eligibility: {e}")
            return False

    def record_promotion_bonus(self, telegram_id: int, promotion_id: int,
                              deposit_id: int, deposit_amount: float,
                              bonus_amount: float) -> bool:
        """Record that a user received a promotion bonus"""
        try:
            # Get user's database ID
            user = self.get_or_create_user(telegram_id, str(telegram_id))
            user_id = user.get('id')

            data = {
                'user': user_id,
                'promotion': promotion_id,
                'deposit': deposit_id,
                'deposit_amount': deposit_amount,
                'bonus_amount': bonus_amount,
                'notes': f'Promotion bonus applied: {bonus_amount}'
            }
            self._post('promotion-eligibility/', data)
            return True
        except Exception as e:
            logger.error(f"Error recording promotion bonus: {e}")
            return False

    # ==================== SUPPORT MESSAGE METHODS ====================

    def create_support_message(self, user_id: int, message: str, is_from_user: bool = True,
                              replied_by: Optional[int] = None) -> Dict:
        """Create new support message"""
        data = {
            'user': user_id,
            'message': message,
            'is_from_user': is_from_user,
            'replied_by': replied_by
        }
        return self._post('support-messages/', data)

    def get_all_support_messages(self) -> List[Dict]:
        """Get all support messages"""
        return self._get('support-messages/')

    # ==================== USER CREDIT METHODS ====================

    def create_user_credit(self, user_id: int, amount: float, credit_type: str,
                          description: str, created_by: int) -> Dict:
        """Create new user credit record"""
        data = {
            'user': user_id,
            'amount': amount,
            'credit_type': credit_type,
            'description': description,
            'created_by': created_by
        }
        return self._post('user-credits/', data)

    def get_all_user_credits(self) -> List[Dict]:
        """Get all user credits"""
        return self._get('user-credits/')

    def get_user_credit(self, telegram_id: int) -> Optional[Dict]:
        """Get a specific user's active credit by telegram_id"""
        try:
            response = self._get(f'user-credits/?user={telegram_id}')
            # Handle paginated response
            if isinstance(response, dict) and 'results' in response:
                credits = response['results']
            else:
                credits = response

            # Return the first active credit (if any)
            if credits and len(credits) > 0:
                return credits[0]
            return None
        except Exception as e:
            logger.error(f"Error getting user credit for {telegram_id}: {e}")
            return None

    def increment_credit_reminder(self, telegram_id: int) -> bool:
        """Increment the reminder count for a user's credit"""
        try:
            credit = self.get_user_credit(telegram_id)
            if not credit:
                return False

            credit_id = credit.get('id')
            current_count = credit.get('reminder_count', 0)

            # Update the reminder count
            self._patch(f'user-credits/{credit_id}/', {'reminder_count': current_count + 1})
            return True
        except Exception as e:
            logger.error(f"Error incrementing reminder for {telegram_id}: {e}")
            return False

    # ==================== EXCHANGE RATE METHODS ====================

    def get_active_exchange_rates(self) -> List[Dict]:
        """Get all active exchange rates"""
        return self._get('exchange-rates/active/')

    def create_exchange_rate(self, currency_from: str, currency_to: str, rate: float) -> Dict:
        """Create new exchange rate"""
        data = {
            'currency_from': currency_from,
            'currency_to': currency_to,
            'rate': rate,
            'is_active': True
        }
        return self._post('exchange-rates/', data)

    def get_all_exchange_rates(self) -> List[Dict]:
        """Get all exchange rates"""
        return self._get('exchange-rates/')

    # ==================== 50-50 INVESTMENT METHODS ====================

    def get_active_investments(self) -> List[Dict]:
        """Get all active investments"""
        return self._get('investments/active/')

    def create_investment(self, pppoker_id: str, investment_amount: float, start_date: str,
                         notes: str = '', user_id: int = None) -> Dict:
        """Create new 50-50 investment (for trusted players, may not be Telegram users)"""
        data = {
            'pppoker_id': pppoker_id,
            'investment_amount': investment_amount,
            'profit_share': 0,
            'loss_share': 0,
            'status': 'Active',
            'start_date': start_date,
            'notes': notes
        }
        # Optional: link to Telegram user if provided
        if user_id:
            data['user'] = user_id
        return self._post('investments/', data)

    def get_all_investments(self) -> List[Dict]:
        """Get all investments"""
        return self._get('investments/')

    def mark_expired_investments_as_lost(self) -> int:
        """Mark investments older than 24 hours as Lost"""
        try:
            result = self._post('investments/mark_expired_as_lost/', {})
            return result.get('marked_count', 0)
        except Exception as e:
            logger.error(f"Error marking expired investments: {e}")
            return 0

    # ==================== CLUB BALANCE METHODS ====================

    def create_club_balance(self, user_id: int, balance: float, notes: str = '') -> Dict:
        """Create or update club balance"""
        data = {
            'user': user_id,
            'balance': balance,
            'notes': notes
        }
        return self._post('club-balances/', data)

    def get_all_club_balances(self) -> List[Dict]:
        """Get all club balances"""
        return self._get('club-balances/')

    # ==================== INVENTORY TRANSACTION METHODS ====================

    def create_inventory_transaction(self, item_name: str, quantity: int, transaction_type: str,
                                    price_per_unit: float, total_amount: float,
                                    created_by: int, notes: str = '') -> Dict:
        """Create new inventory transaction"""
        data = {
            'item_name': item_name,
            'quantity': quantity,
            'transaction_type': transaction_type,
            'price_per_unit': price_per_unit,
            'total_amount': total_amount,
            'notes': notes,
            'created_by': created_by
        }
        return self._post('inventory-transactions/', data)

    def get_all_inventory_transactions(self) -> List[Dict]:
        """Get all inventory transactions"""
        return self._get('inventory-transactions/')


# Create singleton instance
api = DjangoAPI()
