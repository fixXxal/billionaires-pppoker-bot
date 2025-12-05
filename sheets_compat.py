"""
Compatibility layer for legacy Google Sheets API methods
This provides backward compatibility for bot.py while using Django API
"""

from django_api import DjangoAPI
from typing import Dict, List, Optional
import logging
import requests

logger = logging.getLogger(__name__)


class SheetsCompatAPI(DjangoAPI):
    """Extended Django API with legacy Sheets API compatibility methods"""

    # ==================== LEGACY USER METHODS ====================

    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Get user by Telegram ID (legacy method)"""
        return self.get_user_by_telegram_id(telegram_id)

    def get_all_user_ids(self) -> List[int]:
        """Get all user telegram IDs"""
        try:
            users = self.get_all_users()
            return [user.get('telegram_id') for user in users if user.get('telegram_id')]
        except Exception as e:
            logger.error(f"Error getting user IDs: {e}")
            return []

    def update_user_pppoker_id(self, telegram_id: int, pppoker_id: str) -> bool:
        """Update user's PPPoker ID"""
        try:
            user = self.get_user_by_telegram_id(telegram_id)
            if user:
                # Since we don't have a direct update endpoint, we recreate
                self.create_or_update_user(telegram_id, pppoker_id=pppoker_id)
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating PPPoker ID: {e}")
            return False

    def update_user_account_name(self, telegram_id: int, account_name: str) -> bool:
        """Update user's account name - placeholder"""
        # This might not be supported in Django API yet
        return True

    # ==================== LEGACY DEPOSIT METHODS ====================

    def create_deposit_request(self, telegram_id: int, amount: float, method: str,
                              account_name: str, proof_image_path: str, pppoker_id: str) -> Dict:
        """Create deposit request (legacy method)"""
        user = self.get_or_create_user(telegram_id, str(telegram_id), pppoker_id)
        user_id = user.get('id')
        return self.create_deposit(user_id, amount, method, account_name, proof_image_path, pppoker_id)

    def get_deposit_request(self, deposit_id: int) -> Optional[Dict]:
        """Get single deposit by ID"""
        try:
            deposits_response = self.get_all_deposits()

            # Handle paginated response from Django API
            if isinstance(deposits_response, dict) and 'results' in deposits_response:
                deposits = deposits_response['results']
            else:
                deposits = deposits_response

            logger.info(f"Searching for deposit {deposit_id} in {len(deposits)} deposits")

            for deposit in deposits:
                if isinstance(deposit, dict) and deposit.get('id') == deposit_id:
                    logger.info(f"Found deposit {deposit_id}")
                    return deposit

            logger.warning(f"Deposit {deposit_id} not found in {len(deposits)} deposits")
            return None
        except Exception as e:
            logger.error(f"Error getting deposit: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def update_deposit_status(self, deposit_id: int, status: str, admin_id: int = None) -> bool:
        """Update deposit status"""
        try:
            if status.lower() == 'approved':
                self.approve_deposit(deposit_id, admin_id or 0)
            elif status.lower() == 'rejected':
                self.reject_deposit(deposit_id, admin_id or 0)
            return True
        except Exception as e:
            logger.error(f"Error updating deposit status: {e}")
            return False

    def get_deposits_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get deposits within date range"""
        try:
            all_deposits = self.get_all_deposits()
            # Filter by date range if needed
            return all_deposits
        except Exception as e:
            logger.error(f"Error getting deposits by date: {e}")
            return []

    # ==================== LEGACY WITHDRAWAL METHODS ====================

    def create_withdrawal_request(self, telegram_id: int, amount: float, method: str,
                                 account_name: str, account_number: str, pppoker_id: str) -> Dict:
        """Create withdrawal request (legacy method)"""
        user = self.get_or_create_user(telegram_id, str(telegram_id), pppoker_id)
        user_id = user.get('id')
        return self.create_withdrawal(user_id, amount, method, account_name, account_number, pppoker_id)

    def get_withdrawal_request(self, withdrawal_id: int) -> Optional[Dict]:
        """Get single withdrawal by ID"""
        try:
            withdrawals_response = self.get_all_withdrawals()

            # Handle paginated response from Django API
            if isinstance(withdrawals_response, dict) and 'results' in withdrawals_response:
                withdrawals = withdrawals_response['results']
            else:
                withdrawals = withdrawals_response

            logger.info(f"Searching for withdrawal {withdrawal_id} in {len(withdrawals)} withdrawals")

            for withdrawal in withdrawals:
                if isinstance(withdrawal, dict) and withdrawal.get('id') == withdrawal_id:
                    logger.info(f"Found withdrawal {withdrawal_id}")
                    return withdrawal

            logger.warning(f"Withdrawal {withdrawal_id} not found in {len(withdrawals)} withdrawals")
            return None
        except Exception as e:
            logger.error(f"Error getting withdrawal: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def update_withdrawal_status(self, withdrawal_id: int, status: str, admin_id: int = None) -> bool:
        """Update withdrawal status"""
        try:
            if status.lower() == 'approved':
                self.approve_withdrawal(withdrawal_id, admin_id or 0)
            elif status.lower() == 'rejected':
                self.reject_withdrawal(withdrawal_id, admin_id or 0)
            return True
        except Exception as e:
            logger.error(f"Error updating withdrawal status: {e}")
            return False

    def get_withdrawals_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get withdrawals within date range"""
        try:
            return self.get_all_withdrawals()
        except Exception as e:
            logger.error(f"Error getting withdrawals by date: {e}")
            return []

    # ==================== LEGACY JOIN REQUEST METHODS ====================

    def get_join_request(self, request_id: int) -> Optional[Dict]:
        """Get single join request by ID"""
        try:
            requests_response = self.get_all_join_requests()

            # Handle paginated response from Django API
            if isinstance(requests_response, dict) and 'results' in requests_response:
                requests = requests_response['results']
            else:
                requests = requests_response

            logger.info(f"Searching for join request {request_id} in {len(requests)} requests")

            for req in requests:
                if isinstance(req, dict) and req.get('id') == request_id:
                    logger.info(f"Found join request {request_id}")
                    return req

            logger.warning(f"Join request {request_id} not found in {len(requests)} requests")
            return None
        except Exception as e:
            logger.error(f"Error getting join request: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def update_join_request_status(self, request_id: int, status: str, admin_id: int = 0) -> bool:
        """Update join request status"""
        try:
            data = {'status': status}
            if admin_id:
                if status == 'Approved':
                    data['approved_by'] = admin_id
                elif status == 'Rejected':
                    data['rejected_by'] = admin_id

            self._patch(f'join-requests/{request_id}/', data)
            return True
        except Exception as e:
            logger.error(f"Error updating join request {request_id}: {e}")
            return False

    # ==================== LEGACY SEAT REQUEST METHODS ====================

    def get_all_seat_requests(self) -> List[Dict]:
        """Get all seat requests from Django API"""
        return super().get_all_seat_requests()

    def get_seat_request(self, request_id) -> Optional[Dict]:
        """Get single seat request by ID"""
        try:
            # Convert to int if string
            if isinstance(request_id, str):
                request_id = int(request_id)

            requests = self.get_all_seat_requests()
            # Handle paginated response
            if isinstance(requests, dict) and 'results' in requests:
                requests = requests['results']

            for req in requests:
                if req.get('id') == request_id:
                    return req
            return None
        except Exception as e:
            logger.error(f"Error getting seat request: {e}")
            return None

    def settle_seat_request(self, request_id: int, admin_id: int, payment_method: str = 'Seat Payment') -> bool:
        """Settle seat request - creates deposit and marks as completed"""
        try:
            if isinstance(request_id, str):
                request_id = int(request_id)
            super().settle_seat_request(request_id, admin_id, payment_method)
            return True
        except Exception as e:
            logger.error(f"Error settling seat request: {e}")
            return False

    def approve_seat_request(self, request_id: int, admin_id: int) -> bool:
        """Approve seat request"""
        try:
            # Convert to int if string
            if isinstance(request_id, str):
                request_id = int(request_id)

            super().approve_seat_request(request_id, admin_id)
            return True
        except Exception as e:
            logger.error(f"Error approving seat request: {e}")
            return False

    def reject_seat_request(self, request_id: int, admin_id: int, reason: str = '') -> bool:
        """Reject seat request"""
        try:
            # Convert to int if string
            if isinstance(request_id, str):
                request_id = int(request_id)

            super().reject_seat_request(request_id, admin_id, reason)
            return True
        except Exception as e:
            logger.error(f"Error rejecting seat request: {e}")
            return False

    # ==================== LEGACY CASHBACK METHODS ====================

    def check_cashback_eligibility(self, telegram_id: int, promotion_id: int = None,
                                   week_start: str = None, week_end: str = None,
                                   min_deposit: float = 500) -> Dict:
        """Check if user is eligible for cashback based on loss and minimum deposit"""
        # Call parent class method (DjangoAPI)
        return super().check_cashback_eligibility(telegram_id, promotion_id, min_deposit)

    def get_user_pending_cashback(self, telegram_id: int) -> List[Dict]:
        """Get user's pending cashback requests"""
        try:
            all_cashback = self.get_pending_cashback_requests()
            user = self.get_user_by_telegram_id(telegram_id)
            if user:
                user_id = user.get('id')
                return [cb for cb in all_cashback if cb.get('user') == user_id]
            return []
        except Exception as e:
            logger.error(f"Error getting pending cashback: {e}")
            return []

    def approve_cashback_request(self, request_id: int, approved_by: int) -> Dict:
        """Approve a cashback request - delegates to DjangoAPI"""
        return super().approve_cashback_request(request_id, approved_by)

    def reject_cashback_request(self, request_id: int, approved_by: int, rejection_reason: str = '') -> Dict:
        """Reject a cashback request - delegates to DjangoAPI"""
        return super().reject_cashback_request(request_id, approved_by, rejection_reason)

    def get_cashback_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get cashback requests by date range"""
        try:
            return self.get_all_cashback_requests()
        except Exception as e:
            logger.error(f"Error getting cashback by date: {e}")
            return []

    # ==================== LEGACY PROMOTION METHODS ====================

    def create_promotion(self, bonus_percentage: float = None, percentage: float = None,
                        start_date: str = None, end_date: str = None,
                        code: str = None, admin_id: int = None) -> bool:
        """Create deposit bonus promotion - supports multiple parameter formats for backward compatibility"""
        try:
            # Handle different parameter formats
            promo_percentage = bonus_percentage or percentage
            if not promo_percentage:
                raise ValueError("Either bonus_percentage or percentage must be provided")

            # Auto-generate code if not provided (like BONUS_2025)
            if not code:
                from datetime import datetime
                code = f"BONUS_{datetime.now().year}"

            self.create_promo_code(code, promo_percentage, start_date, end_date, promo_type='bonus')
            return True
        except Exception as e:
            logger.error(f"Error creating promotion: {e}")
            return False

    def get_active_promotion(self) -> Optional[Dict]:
        """Get active deposit bonus promotion"""
        try:
            promos = self.get_active_promo_codes(promo_type='bonus')
            return promos[0] if promos else None
        except Exception as e:
            logger.error(f"Error getting active promotion: {e}")
            return None

    def check_user_promotion_eligibility(self, telegram_id: int, pppoker_id: str = None,
                                        promotion_id: int = None) -> bool:
        """Check if user is eligible for promotion (hasn't received bonus from this promo yet)"""
        if not promotion_id:
            return True  # If no promotion_id provided, assume eligible
        # Call parent class method (DjangoAPI)
        return super().check_user_promotion_eligibility(telegram_id, promotion_id)

    def record_promotion_bonus(self, user_id: int = None, telegram_id: int = None,
                              pppoker_id: str = None, promotion_id: int = None,
                              deposit_request_id: int = None, deposit_amount: float = None,
                              bonus_amount: float = None, amount: float = None,
                              promo_code: str = None) -> bool:
        """Record promotion bonus - supports multiple parameter formats for backward compatibility"""
        try:
            # Handle different parameter formats
            tid = telegram_id or user_id
            dep_amount = deposit_amount or amount

            if not tid or not promotion_id or not dep_amount or not bonus_amount:
                logger.error(f"Missing required parameters for recording promotion bonus")
                return False

            # Call parent class method (DjangoAPI)
            return super().record_promotion_bonus(
                telegram_id=tid,
                promotion_id=promotion_id,
                deposit_id=deposit_request_id or 0,  # May be 0 if deposit not yet created
                deposit_amount=dep_amount,
                bonus_amount=bonus_amount
            )
        except Exception as e:
            logger.error(f"Error recording promotion bonus: {e}")
            return False

    def create_cashback_promotion(self, cashback_percentage: float = None, percentage: float = None,
                                 start_date: str = None, end_date: str = None,
                                 code: str = None, admin_id: int = None) -> bool:
        """Create cashback promotion - supports multiple parameter formats for backward compatibility"""
        try:
            # Handle different parameter formats
            promo_percentage = cashback_percentage or percentage
            if not promo_percentage:
                raise ValueError("Either cashback_percentage or percentage must be provided")

            # Auto-generate code if not provided (like CASHBACK_2025)
            if not code:
                from datetime import datetime
                code = f"CASHBACK_{datetime.now().year}"

            self.create_promo_code(code, promo_percentage, start_date, end_date, promo_type='cashback')
            return True
        except Exception as e:
            logger.error(f"Error creating cashback promotion: {e}")
            return False

    def get_active_cashback_promotion(self) -> Optional[Dict]:
        """Get active cashback promotion"""
        try:
            promos = self.get_active_promo_codes(promo_type='cashback')
            return promos[0] if promos else None
        except Exception as e:
            logger.error(f"Error getting active cashback promotion: {e}")
            return None

    def get_all_promotions(self) -> List[Dict]:
        """Get all deposit bonus promotions"""
        try:
            all_promos = self.get_all_promo_codes()
            # Handle paginated response or direct list
            if isinstance(all_promos, dict) and 'results' in all_promos:
                all_promos = all_promos['results']
            elif not isinstance(all_promos, list):
                return []
            # Filter for bonus type only
            return [p for p in all_promos if isinstance(p, dict) and p.get('promo_type') == 'bonus']
        except Exception as e:
            logger.error(f"Error getting all promotions: {e}")
            return []

    def get_all_cashback_promotions(self) -> List[Dict]:
        """Get all cashback promotions"""
        try:
            all_promos = self.get_all_promo_codes()
            # Handle paginated response or direct list
            if isinstance(all_promos, dict) and 'results' in all_promos:
                all_promos = all_promos['results']
            elif not isinstance(all_promos, list):
                return []
            # Filter for cashback type only
            return [p for p in all_promos if isinstance(p, dict) and p.get('promo_type') == 'cashback']
        except Exception as e:
            logger.error(f"Error getting all cashback promotions: {e}")
            return []

    def get_bonuses_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get bonuses by date range - placeholder"""
        return []

    # ==================== LEGACY PAYMENT ACCOUNT METHODS ====================

    def get_payment_account(self, method: str) -> Optional[Dict]:
        """Get payment account by method"""
        try:
            accounts = self.get_active_payment_accounts()
            for account in accounts:
                if account.get('method', '').lower() == method.lower():
                    return account
            return None
        except Exception as e:
            logger.error(f"Error getting payment account: {e}")
            return None

    def get_payment_account_details(self, method: str) -> Optional[str]:
        """Get payment account number"""
        account = self.get_payment_account(method)
        return account.get('account_number') if account else None

    def get_payment_account_holder(self, method: str) -> Optional[str]:
        """Get payment account holder name"""
        account = self.get_payment_account(method)
        return account.get('account_name') if account else None

    def get_all_payment_accounts(self) -> Dict:
        """Get all payment accounts in legacy format (dict keyed by method)"""
        try:
            # Get response from Django API
            response = super().get_all_payment_accounts()
            logger.info(f"Raw response from Django API: {response}, type: {type(response)}")

            # Handle paginated response from Django REST framework
            if isinstance(response, dict) and 'results' in response:
                accounts_list = response['results']
                logger.info(f"Extracted {len(accounts_list)} accounts from paginated response")
            elif isinstance(response, list):
                accounts_list = response
            else:
                logger.warning(f"Unexpected response format: {response}")
                return {}

            # Handle empty or None response
            if not accounts_list:
                logger.warning("No payment accounts returned from API")
                return {}

            # Convert to legacy dict format: {'BML': {...}, 'MIB': {...}}
            accounts_dict = {}
            for account in accounts_list:
                if isinstance(account, dict) and 'method' in account:
                    method = account['method']
                    accounts_dict[method] = account
                    logger.info(f"Added {method} to accounts dict: {account}")
                else:
                    logger.warning(f"Skipping invalid account: {account}")

            logger.info(f"Final accounts_dict: {accounts_dict}")
            return accounts_dict
        except Exception as e:
            logger.error(f"Error getting all payment accounts: {e}", exc_info=True)
            return {}

    def update_payment_account(self, method: str, account_number: str, account_name: str = None) -> bool:
        """Update payment account"""
        try:
            # Call parent DjangoAPI method which handles update-or-create
            super().update_payment_account(method, account_number, account_name)
            return True
        except Exception as e:
            logger.error(f"Error updating payment account: {e}", exc_info=True)
            raise  # Re-raise so bot shows error to admin

    def clear_payment_account(self, method: str) -> bool:
        """Deactivate a payment account - delegates to DjangoAPI"""
        return super().clear_payment_account(method)

    # ==================== LEGACY COUNTER STATUS METHODS ====================

    def set_counter_status(self, status: str, admin_id: int = None, announcement_sent: bool = True) -> bool:
        """Set counter status"""
        try:
            current = self.get_counter_status()
            is_currently_open = current.get('is_open', True)
            target_open = status.lower() in ['open', 'opened', 'true', '1']

            # Only toggle if status is different
            if is_currently_open != target_open:
                self.toggle_counter(admin_id or 0)
            return True
        except Exception as e:
            logger.error(f"Error setting counter status: {e}")
            return False

    # ==================== LEGACY SPIN METHODS ====================

    def update_spin_user(self, telegram_id: int, **kwargs) -> bool:
        """Update spin user with new data"""
        try:
            # Get the user's database ID first
            user = self.get_or_create_user(telegram_id, kwargs.get('username', 'User'))
            if not user:
                logger.error(f"Failed to get user for telegram_id {telegram_id}")
                return False

            user_id = user['id']

            # Build update data
            update_data = {}
            if 'available_spins' in kwargs:
                update_data['available_spins'] = kwargs['available_spins']
            if 'total_spins_used' in kwargs:
                update_data['total_spins_used'] = kwargs['total_spins_used']
            if 'total_chips_earned' in kwargs:
                update_data['total_chips_earned'] = kwargs['total_chips_earned']

            if not update_data:
                logger.warning(f"No spin data to update for user {telegram_id}")
                return False

            # Get existing spin user
            spin_user = self.get_spin_user(telegram_id)
            if not spin_user:
                logger.error(f"Spin user not found for telegram_id {telegram_id}")
                return False

            spin_user_id = spin_user['id']

            # Update via Django API
            response = requests.patch(
                f"{self.base_url}/spin-users/{spin_user_id}/",
                json=update_data,
                timeout=10
            )

            if response.status_code in [200, 204]:
                logger.info(f"Successfully updated spin user {telegram_id}: {update_data}")
                return True
            else:
                logger.error(f"Failed to update spin user: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error updating spin user: {e}")
            return False

    def get_spin_by_id(self, spin_id: int) -> Optional[Dict]:
        """Get spin by ID"""
        try:
            history = self.get_all_spin_history()
            for spin in history:
                if spin.get('id') == spin_id:
                    return spin
            return None
        except Exception as e:
            logger.error(f"Error getting spin: {e}")
            return None

    def get_spins_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get spins by date range"""
        try:
            return self.get_all_spin_history()
        except Exception as e:
            logger.error(f"Error getting spins by date: {e}")
            return []

    # ==================== LEGACY ADMIN METHODS ====================

    def add_admin(self, telegram_id: int, username: str) -> bool:
        """Add admin"""
        try:
            self.create_admin(telegram_id, username)
            return True
        except Exception as e:
            logger.error(f"Error adding admin: {e}")
            return False

    def remove_admin(self, telegram_id: int) -> bool:
        """Remove admin - placeholder"""
        return True

    # ==================== LEGACY USER CREDIT METHODS ====================

    def add_user_credit(self, telegram_id: int, username_or_amount, pppoker_id_or_credit_type,
                       amount_or_description, request_id_or_created_by) -> bool:
        """Add user credit - supports both old and new signatures for backward compatibility"""
        try:
            # Check if it's the old signature (telegram_id, username, pppoker_id, amount, request_id)
            # or new signature (telegram_id, amount, credit_type, description, created_by)
            if isinstance(username_or_amount, str):
                # Old signature from seat request: (telegram_id, username, pppoker_id, amount, request_id)
                username = username_or_amount
                pppoker_id = pppoker_id_or_credit_type
                amount = amount_or_description
                request_id = request_id_or_created_by

                user = self.get_or_create_user(telegram_id, username)
                user_id = user.get('id')

                # Update user's PPPoker ID if provided
                if pppoker_id and pppoker_id != 'N/A':
                    try:
                        self._patch(f'users/{user_id}/', {'pppoker_id': pppoker_id})
                        logger.info(f"Updated user {telegram_id} PPPoker ID to {pppoker_id}")
                    except Exception as e:
                        logger.error(f"Failed to update user PPPoker ID: {e}")

                credit_type = 'Seat Payment'
                description = f"Seat request {request_id} for PPPoker ID {pppoker_id}"
                created_by = 0  # System created

                self.create_user_credit(user_id, amount, credit_type, description, created_by)
                return True
            else:
                # New signature: (telegram_id, amount, credit_type, description, created_by)
                amount = username_or_amount
                credit_type = pppoker_id_or_credit_type
                description = amount_or_description
                created_by = request_id_or_created_by

                user = self.get_or_create_user(telegram_id, str(telegram_id))
                user_id = user.get('id')
                self.create_user_credit(user_id, amount, credit_type, description, created_by)
                return True
        except Exception as e:
            logger.error(f"Error adding user credit: {e}")
            return False

    def get_user_credit(self, telegram_id: int):
        """Get user's active credit by telegram_id"""
        # SheetsCompatAPI extends DjangoAPI, so we can call parent method directly
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

    def clear_user_credit(self, telegram_id: int) -> bool:
        """Delete user's active credit from database"""
        try:
            credit = self.get_user_credit(telegram_id)
            if not credit:
                return True  # No credit to clear

            credit_id = credit.get('id')
            # Delete the credit record
            self._delete(f'user-credits/{credit_id}/')
            return True
        except Exception as e:
            logger.error(f"Error clearing user credit for {telegram_id}: {e}")
            return False

    def get_all_active_credits(self) -> List[Dict]:
        """Get all active credits"""
        try:
            return self.get_all_user_credits()
        except Exception as e:
            logger.error(f"Error getting active credits: {e}")
            return []

    def increment_credit_reminder(self, telegram_id: int) -> bool:
        """Increment credit reminder count"""
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

    def get_daily_credit_summary(self, date: str) -> Dict:
        """Get daily credit summary - placeholder"""
        return {'total': 0, 'count': 0}

    # ==================== LEGACY EXCHANGE RATE METHODS ====================

    def get_exchange_rate(self, currency_from: str, currency_to: str) -> Optional[float]:
        """Get exchange rate"""
        try:
            rates = self.get_active_exchange_rates()
            for rate in rates:
                if (rate.get('currency_from') == currency_from and
                    rate.get('currency_to') == currency_to):
                    return rate.get('rate')
            return None
        except Exception as e:
            logger.error(f"Error getting exchange rate: {e}")
            return None

    def set_exchange_rate(self, currency_from: str, currency_to: str, rate: float) -> bool:
        """Set exchange rate"""
        try:
            self.create_exchange_rate(currency_from, currency_to, rate)
            return True
        except Exception as e:
            logger.error(f"Error setting exchange rate: {e}")
            return False

    # ==================== LEGACY INVESTMENT METHODS ====================

    def add_investment(self, telegram_id: int, amount: float, start_date: str, notes: str = '', pppoker_id: str = None) -> bool:
        """Add 50-50 investment (legacy method - requires telegram_id)"""
        try:
            user = self.get_or_create_user(telegram_id, str(telegram_id))
            user_id = user.get('id')

            # Use provided PPPoker ID or get from user's deposits
            if pppoker_id is None:
                pppoker_id = self.get_pppoker_id_from_deposits(telegram_id) or 'UNKNOWN'
            elif not pppoker_id:
                pppoker_id = 'UNKNOWN'

            # Create investment using inherited method from DjangoAPI
            self.create_investment(
                pppoker_id=pppoker_id,
                investment_amount=amount,
                start_date=start_date,
                notes=notes,
                user_id=user_id
            )
            return True
        except Exception as e:
            logger.error(f"Error adding investment: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_active_investments_by_id(self, telegram_id: int) -> List[Dict]:
        """Get user's active investments"""
        try:
            all_investments = self.get_active_investments()
            user = self.get_user_by_telegram_id(telegram_id)
            if user:
                user_id = user.get('id')
                return [inv for inv in all_investments if inv.get('user') == user_id]
            return []
        except Exception as e:
            logger.error(f"Error getting user investments: {e}")
            return []

    def get_all_active_investments_summary(self) -> List[Dict]:
        """Get summary of all active investments grouped by PPPoker ID"""
        try:
            investments = self.get_active_investments()

            # Group investments by PPPoker ID
            grouped = {}
            for inv in investments:
                pppoker_id = inv.get('pppoker_id', 'UNKNOWN')

                if pppoker_id not in grouped:
                    grouped[pppoker_id] = {
                        'pppoker_id': pppoker_id,
                        'player_note': inv.get('notes', ''),
                        'total_amount': 0,
                        'first_date': inv.get('start_date', ''),
                        'investments': []
                    }

                # Add to total amount (ensure it's a float)
                amount = inv.get('investment_amount', 0)
                if isinstance(amount, str):
                    amount = float(amount)
                grouped[pppoker_id]['total_amount'] += amount
                grouped[pppoker_id]['investments'].append(inv)

                # Keep the earliest date
                current_date = grouped[pppoker_id]['first_date']
                new_date = inv.get('start_date', '')
                if not current_date or (new_date and new_date < current_date):
                    grouped[pppoker_id]['first_date'] = new_date

            return list(grouped.values())
        except Exception as e:
            logger.error(f"Error getting investment summary: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_active_investments_by_pppoker_id(self, pppoker_id: str) -> Dict:
        """Get active investments for a specific PPPoker ID with summary info"""
        try:
            all_investments = self.get_active_investments()
            investments = [inv for inv in all_investments if inv.get('pppoker_id') == pppoker_id]

            if not investments:
                return {
                    'count': 0,
                    'total_amount': 0,
                    'investments': []
                }

            # Calculate total investment amount
            total_amount = 0
            for inv in investments:
                amount = inv.get('investment_amount', 0)
                if isinstance(amount, str):
                    amount = float(amount)
                total_amount += amount

            return {
                'count': len(investments),
                'total_amount': total_amount,
                'investments': investments
            }
        except Exception as e:
            logger.error(f"Error getting investments by PPPoker ID {pppoker_id}: {e}")
            import traceback
            traceback.print_exc()
            return {
                'count': 0,
                'total_amount': 0,
                'investments': []
            }

    def record_investment_return(self, pppoker_id: str, return_amount: float) -> Dict:
        """Record investment return and calculate profit/loss split"""
        try:
            from datetime import datetime

            # Get all active investments for this PPPoker ID
            all_investments = self.get_active_investments()
            investments = [inv for inv in all_investments if inv.get('pppoker_id') == pppoker_id]

            if not investments:
                return {
                    'success': False,
                    'error': f'No active investments found for PPPoker ID: {pppoker_id}'
                }

            # Calculate total investment
            total_investment = 0
            for inv in investments:
                amount = inv.get('investment_amount', 0)
                if isinstance(amount, str):
                    amount = float(amount)
                total_investment += amount

            # Calculate profit/loss
            net_profit = return_amount - total_investment

            # 50/50 split
            club_share = total_investment + (net_profit / 2)  # Club gets initial back + 50% of profit
            player_share = net_profit / 2  # Player gets 50% of profit

            # Update all investments to Completed
            today = datetime.now().strftime('%Y-%m-%d')

            for inv in investments:
                inv_id = inv.get('id')
                # Update investment status using PATCH for partial update
                self._patch(f"investments/{inv_id}/", {
                    'status': 'Completed',
                    'profit_share': float(player_share / len(investments)),  # Split evenly across all investments
                    'loss_share': 0 if net_profit >= 0 else abs(net_profit) / len(investments),
                    'end_date': today
                })

            return {
                'success': True,
                'net_profit': net_profit,
                'player_share': player_share,
                'club_share': club_share,
                'total_investment': total_investment,
                'return_amount': return_amount
            }

        except Exception as e:
            logger.error(f"Error recording investment return: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }

    def mark_expired_investments_as_lost(self) -> int:
        """Mark expired investments as lost - placeholder"""
        return 0

    def get_investment_stats(self) -> Dict:
        """Get investment statistics - placeholder"""
        return {'total_active': 0, 'total_amount': 0}

    # ==================== LEGACY CLUB BALANCE METHODS ====================

    def get_club_balances(self) -> List[Dict]:
        """Get all club balances"""
        try:
            return self.get_all_club_balances()
        except Exception as e:
            logger.error(f"Error getting club balances: {e}")
            return []

    def set_starting_balances(self, telegram_id: int, balance: float) -> bool:
        """Set starting balance for user"""
        try:
            user = self.get_or_create_user(telegram_id, str(telegram_id))
            user_id = user.get('id')
            self.create_club_balance(user_id, balance)
            return True
        except Exception as e:
            logger.error(f"Error setting starting balance: {e}")
            return False

    def buy_chips_for_club(self, amount: float, notes: str, created_by: int) -> bool:
        """Buy chips for club - placeholder"""
        return True

    def add_cash_to_club(self, amount: float, notes: str, created_by: int) -> bool:
        """Add cash to club - placeholder"""
        return True

    # ==================== LEGACY OCR/IMAGE PROCESSING ====================

    def process_receipt_image(self, image_path: str) -> Dict:
        """Process receipt image - placeholder"""
        return {'success': False, 'amount': 0}

    def format_extracted_details(self, details: Dict) -> str:
        """Format extracted details"""
        return str(details)

    # ==================== LEGACY REPORTING ====================

    def save_all_reports(self) -> bool:
        """Save all reports - placeholder"""
        return True

    def save_counter_poster(self, poster_path: str) -> bool:
        """Save counter poster - placeholder"""
        return True

    def get_saved_poster(self) -> Optional[str]:
        """Get saved poster path"""
        return None

    def get_pppoker_id_from_deposits(self, telegram_id: int) -> Optional[str]:
        """Get PPPoker ID from user's deposits"""
        try:
            user = self.get_user_by_telegram_id(telegram_id)
            if user:
                return user.get('pppoker_id')
            return None
        except Exception as e:
            logger.error(f"Error getting PPPoker ID: {e}")
            return None
