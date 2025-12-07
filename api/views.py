"""
Django REST Framework API Views
All API endpoints for Billionaires PPPoker Bot
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required

from .models import (
    User, Deposit, Withdrawal, SpinUser, SpinAward, SpinUsage, SpinHistory,
    JoinRequest, SeatRequest, CashbackRequest, PaymentAccount,
    Admin, CounterStatus, PromoCode, PromotionEligibility, CashbackEligibility,
    SupportMessage, UserCredit, ExchangeRate, FiftyFiftyInvestment,
    ClubBalance, InventoryTransaction, NotificationMessage
)
from .serializers import (
    UserSerializer, DepositSerializer, WithdrawalSerializer,
    SpinUserSerializer, SpinAwardSerializer, SpinUsageSerializer, SpinHistorySerializer,
    JoinRequestSerializer, SeatRequestSerializer, CashbackRequestSerializer,
    PaymentAccountSerializer, AdminSerializer, CounterStatusSerializer, PromoCodeSerializer,
    PromotionEligibilitySerializer, CashbackEligibilitySerializer,
    SupportMessageSerializer, UserCreditSerializer, ExchangeRateSerializer,
    FiftyFiftyInvestmentSerializer, ClubBalanceSerializer,
    InventoryTransactionSerializer, NotificationMessageSerializer
)


def health_check(request):
    """Simple health check endpoint for Railway deployment"""
    return JsonResponse({'status': 'healthy', 'service': 'billionaires-api'})


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Users

    list: Get all users
    retrieve: Get specific user by ID
    create: Create new user
    update: Update user
    destroy: Delete user
    get_by_telegram_id: Get user by Telegram ID (custom action)
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(detail=False, methods=['get', 'post'])
    def by_telegram_id(self, request):
        """Get or create user by Telegram ID"""
        telegram_id = request.data.get('telegram_id') or request.query_params.get('telegram_id')

        if not telegram_id:
            return Response(
                {'error': 'telegram_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.method == 'POST':
            # Get or create user, and always update username if provided
            user, created = User.objects.get_or_create(
                telegram_id=telegram_id,
                defaults={
                    'username': request.data.get('username', f'User{telegram_id}'),
                    'pppoker_id': request.data.get('pppoker_id', ''),
                }
            )

            # Always update username if provided (in case user changed their Telegram username)
            # ALSO update if current username is a default/placeholder (like "User" or "User123456")
            new_username = request.data.get('username')
            if not created and new_username:
                # Update if: new username provided AND (current is default OR new is better)
                is_current_default = (user.username.startswith('User') or
                                     user.username.startswith('user_') or
                                     user.username == 'User')
                if is_current_default or user.username != new_username:
                    user.username = new_username
                    user.save(update_fields=['username'])

            serializer = self.get_serializer(user)
            return Response({
                'user': serializer.data,
                'created': created
            })
        else:
            # GET request
            try:
                user = User.objects.get(telegram_id=telegram_id)
                serializer = self.get_serializer(user)
                return Response(serializer.data)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )


class DepositViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Deposits

    list: Get all deposits
    pending: Get pending deposits (admin)
    approve: Approve deposit (admin)
    reject: Reject deposit (admin)
    """
    queryset = Deposit.objects.all()
    serializer_class = DepositSerializer

    def get_queryset(self):
        """Filter deposits by user telegram_id if provided"""
        queryset = super().get_queryset()
        telegram_id = self.request.query_params.get('user')
        if telegram_id:
            queryset = queryset.filter(user__telegram_id=telegram_id)
        return queryset

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending deposits"""
        deposits = Deposit.objects.filter(status='Pending')
        serializer = self.get_serializer(deposits, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a deposit"""
        deposit = self.get_object()
        admin_id = request.data.get('admin_id')
        add_balance = request.data.get('add_balance', True)  # Default to True for backward compatibility

        if not admin_id:
            return Response(
                {'error': 'admin_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        deposit.status = 'Approved'
        deposit.approved_at = timezone.now()
        deposit.approved_by = admin_id
        deposit.synced_to_sheets = False  # Mark for sync
        deposit.save()

        # Update user balance (skip if add_balance is False, e.g., for credit payment tracking)
        if add_balance:
            deposit.user.balance += deposit.amount
            deposit.user.synced_to_sheets = False
            deposit.user.save()

        serializer = self.get_serializer(deposit)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a deposit"""
        deposit = self.get_object()
        admin_id = request.data.get('admin_id')
        reason = request.data.get('reason', '')

        if not admin_id:
            return Response(
                {'error': 'admin_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        deposit.status = 'Rejected'
        deposit.approved_at = timezone.now()
        deposit.approved_by = admin_id
        deposit.rejection_reason = reason
        deposit.synced_to_sheets = False
        deposit.save()

        serializer = self.get_serializer(deposit)
        return Response(serializer.data)


class WithdrawalViewSet(viewsets.ModelViewSet):
    """API endpoint for Withdrawals"""
    queryset = Withdrawal.objects.all()
    serializer_class = WithdrawalSerializer

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending withdrawals"""
        withdrawals = Withdrawal.objects.filter(status='Pending')
        serializer = self.get_serializer(withdrawals, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a withdrawal"""
        withdrawal = self.get_object()
        admin_id = request.data.get('admin_id')

        if not admin_id:
            return Response(
                {'error': 'admin_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user has enough balance
        if withdrawal.user.balance < withdrawal.amount:
            return Response(
                {'error': 'Insufficient balance'},
                status=status.HTTP_400_BAD_REQUEST
            )

        withdrawal.status = 'Approved'
        withdrawal.approved_at = timezone.now()
        withdrawal.approved_by = admin_id
        withdrawal.synced_to_sheets = False
        withdrawal.save()

        # Deduct from user balance
        withdrawal.user.balance -= withdrawal.amount
        withdrawal.user.synced_to_sheets = False
        withdrawal.user.save()

        serializer = self.get_serializer(withdrawal)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a withdrawal"""
        withdrawal = self.get_object()
        admin_id = request.data.get('admin_id')
        reason = request.data.get('reason', '')

        if not admin_id:
            return Response(
                {'error': 'admin_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        withdrawal.status = 'Rejected'
        withdrawal.approved_at = timezone.now()
        withdrawal.approved_by = admin_id
        withdrawal.rejection_reason = reason
        withdrawal.synced_to_sheets = False
        withdrawal.save()

        serializer = self.get_serializer(withdrawal)
        return Response(serializer.data)


class SpinUserViewSet(viewsets.ModelViewSet):
    """API endpoint for Spin Users"""
    queryset = SpinUser.objects.all()
    serializer_class = SpinUserSerializer

    @action(detail=False, methods=['get', 'post'])
    def by_telegram_id(self, request):
        """Get or create spin user by Telegram ID"""
        telegram_id = request.data.get('telegram_id') or request.query_params.get('telegram_id')

        if not telegram_id:
            return Response(
                {'error': 'telegram_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(telegram_id=telegram_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        spin_user, created = SpinUser.objects.get_or_create(
            user=user,
            defaults={'available_spins': 0}
        )

        serializer = self.get_serializer(spin_user)
        return Response({
            'spin_user': serializer.data,
            'created': created
        })

    @action(detail=True, methods=['post'])
    def add_spins(self, request, pk=None):
        """Add spins to user"""
        spin_user = self.get_object()
        spins_to_add = request.data.get('spins', 0)

        spin_user.available_spins += spins_to_add
        spin_user.synced_to_sheets = False
        spin_user.save()

        serializer = self.get_serializer(spin_user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get spin bot statistics"""
        from django.db.models import Sum

        try:
            # Total users with spins
            total_users = SpinUser.objects.count()

            # Total spins used across all users
            total_spins_used = SpinUser.objects.aggregate(
                total=Sum('total_spins_used')
            )['total'] or 0

            # Total chips awarded across all users
            total_chips_awarded = SpinUser.objects.aggregate(
                total=Sum('total_chips_earned')
            )['total'] or 0

            # Pending rewards count
            pending_rewards = SpinHistory.objects.filter(status='Pending').count()

            # Approved rewards count
            approved_rewards = SpinHistory.objects.filter(status='Approved').count()

            # Top 5 users by total spins used
            top_users = SpinUser.objects.order_by('-total_spins_used')[:5]
            top_users_data = []
            for spin_user in top_users:
                top_users_data.append({
                    'username': spin_user.user.username if spin_user.user else 'Unknown',
                    'total_spins': spin_user.total_spins_used,
                    'total_chips': spin_user.total_chips_earned
                })

            return Response({
                'total_users': total_users,
                'total_spins_used': total_spins_used,
                'total_chips_awarded': total_chips_awarded,
                'pending_rewards': pending_rewards,
                'approved_rewards': approved_rewards,
                'top_users': top_users_data
            })

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SpinAwardViewSet(viewsets.ModelViewSet):
    """API endpoint for Spin Awards - tracks when spins are given"""
    queryset = SpinAward.objects.all()
    serializer_class = SpinAwardSerializer

    @action(detail=False, methods=['get'])
    def by_user(self, request):
        """Get spin awards for a specific user by telegram_id"""
        telegram_id = request.query_params.get('telegram_id')

        if not telegram_id:
            return Response(
                {'error': 'telegram_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(telegram_id=telegram_id)
            awards = SpinAward.objects.filter(user=user)
            serializer = self.get_serializer(awards, many=True)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def by_deposit(self, request):
        """Get spin awards for a specific deposit"""
        deposit_id = request.query_params.get('deposit_id')

        if not deposit_id:
            return Response(
                {'error': 'deposit_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        awards = SpinAward.objects.filter(deposit_id=deposit_id)
        serializer = self.get_serializer(awards, many=True)
        return Response(serializer.data)


class SpinUsageViewSet(viewsets.ModelViewSet):
    """API endpoint for Spin Usages - tracks when spins are played"""
    queryset = SpinUsage.objects.all()
    serializer_class = SpinUsageSerializer

    @action(detail=False, methods=['get'])
    def by_user(self, request):
        """Get spin usages for a specific user by telegram_id"""
        telegram_id = request.query_params.get('telegram_id')

        if not telegram_id:
            return Response(
                {'error': 'telegram_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(telegram_id=telegram_id)
            usages = SpinUsage.objects.filter(user=user)
            serializer = self.get_serializer(usages, many=True)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def by_award(self, request):
        """Get spin usages for a specific award"""
        award_id = request.query_params.get('award_id')

        if not award_id:
            return Response(
                {'error': 'award_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        usages = SpinUsage.objects.filter(spin_award_id=award_id)
        serializer = self.get_serializer(usages, many=True)
        return Response(serializer.data)


class SpinHistoryViewSet(viewsets.ModelViewSet):
    """API endpoint for Spin History (LEGACY - kept for backward compatibility)"""
    queryset = SpinHistory.objects.all()
    serializer_class = SpinHistorySerializer
    filterset_fields = ['status', 'notified_at']  # Enable filtering by status and notified_at

    def get_queryset(self):
        """Override to support query parameter filtering"""
        queryset = SpinHistory.objects.all()

        # Filter by status if provided
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by notified_at__isnull if provided
        notified_at_isnull = self.request.query_params.get('notified_at__isnull')
        if notified_at_isnull is not None:
            # Convert string 'true'/'false' to boolean
            is_null = notified_at_isnull.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(notified_at__isnull=is_null)

        return queryset

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending spin rewards"""
        spins = SpinHistory.objects.filter(status='Pending')
        serializer = self.get_serializer(spins, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_notified(self, request, pk=None):
        """Mark a spin as notified - CRITICAL endpoint for notification system"""
        from django.utils import timezone
        import logging
        logger = logging.getLogger(__name__)

        spin = self.get_object()
        notified_at = request.data.get('notified_at')

        if not notified_at:
            return Response(
                {'error': 'notified_at is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # CRITICAL: Don't mark as notified if already approved/rejected
        # This prevents re-notifying about already-processed spins
        if spin.status != 'Pending':
            logger.warning(f"⚠️ Refusing to mark spin {pk} as notified - status is {spin.status}, not Pending")
            return Response(
                {
                    'warning': f'Spin {pk} is already {spin.status}, not marked as notified',
                    'status': spin.status,
                    'notified_at': spin.notified_at
                },
                status=status.HTTP_200_OK  # Return 200 to avoid errors, but with warning
            )

        try:
            # Parse the datetime string
            from datetime import datetime
            if isinstance(notified_at, str):
                notified_at = datetime.fromisoformat(notified_at.replace('Z', '+00:00'))

            # Update and save
            spin.notified_at = notified_at
            spin.save(update_fields=['notified_at'])

            logger.info(f"✅ Successfully marked spin {pk} (status={spin.status}) as notified at {notified_at}")

            # Return updated object to confirm
            serializer = self.get_serializer(spin)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"❌ Failed to mark spin {pk} as notified: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def process_spin(self, request):
        """Process one or more spins"""
        import logging
        logger = logging.getLogger(__name__)

        telegram_id = request.data.get('telegram_id')
        spin_count = request.data.get('spin_count', 1)
        results = request.data.get('results', [])
        username = request.data.get('username')  # Get username from request

        logger.info(f"🎰 process_spin called: telegram_id={telegram_id}, username={username}, spin_count={spin_count}")

        if not telegram_id:
            return Response(
                {'error': 'telegram_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(telegram_id=telegram_id)
            spin_user = SpinUser.objects.get(user=user)

            logger.info(f"📝 Current user in DB: id={user.telegram_id}, username={user.username}")
            logger.info(f"📝 Username from request: {username}")

            # Update username if provided (user may have changed their Telegram username)
            # ALSO update if current username is a default/placeholder
            if username:
                is_current_default = (user.username.startswith('User') or
                                     user.username.startswith('user_') or
                                     user.username == 'User')
                if is_current_default or user.username != username:
                    logger.info(f"✏️ Updating username from '{user.username}' to '{username}'")
                    user.username = username
                    user.save(update_fields=['username'])
                    logger.info(f"✅ Username updated successfully")
                else:
                    logger.info(f"⏭️ Username unchanged (already '{user.username}')")
            else:
                logger.warning(f"⚠️ No username provided in request! User.username will not be updated.")

        except (User.DoesNotExist, SpinUser.DoesNotExist):
            return Response(
                {'error': 'User or SpinUser not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user has enough spins
        if spin_user.available_spins < spin_count:
            return Response(
                {'error': 'Not enough spins available'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create spin history records
        spin_records = []
        for result in results:
            spin_record = SpinHistory.objects.create(
                user=user,
                prize=result['prize'],
                chips=result['chips'],
                pppoker_id=user.pppoker_id,
                status='Auto' if result['chips'] == 0 else 'Pending',
                synced_to_sheets=False
            )
            spin_records.append(spin_record)

        # Update spin user
        spin_user.available_spins -= spin_count
        spin_user.total_spins_used += spin_count
        spin_user.synced_to_sheets = False
        spin_user.save()

        serializer = self.get_serializer(spin_records, many=True)
        return Response({
            'spins': serializer.data,
            'available_spins': spin_user.available_spins
        })

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a spin reward"""
        spin = self.get_object()
        admin_id = request.data.get('admin_id')

        if not admin_id:
            return Response(
                {'error': 'admin_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        spin.status = 'Approved'
        spin.approved_at = timezone.now()
        spin.approved_by = admin_id
        spin.synced_to_sheets = False
        spin.save()

        # Update user's spin earnings
        spin_user = SpinUser.objects.get(user=spin.user)
        spin_user.total_chips_earned += spin.chips
        spin_user.synced_to_sheets = False
        spin_user.save()

        serializer = self.get_serializer(spin)
        return Response(serializer.data)


class JoinRequestViewSet(viewsets.ModelViewSet):
    """API endpoint for Join Requests"""
    queryset = JoinRequest.objects.all()
    serializer_class = JoinRequestSerializer

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending join requests"""
        joins = JoinRequest.objects.filter(status='Pending')
        serializer = self.get_serializer(joins, many=True)
        return Response(serializer.data)


class SeatRequestViewSet(viewsets.ModelViewSet):
    """API endpoint for Seat Requests"""
    queryset = SeatRequest.objects.all()
    serializer_class = SeatRequestSerializer

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending seat requests"""
        seats = SeatRequest.objects.filter(status='Pending')
        serializer = self.get_serializer(seats, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a seat request"""
        seat_request = self.get_object()
        admin_id = request.data.get('admin_id')

        if not admin_id:
            return Response(
                {'error': 'admin_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        seat_request.status = 'Approved'
        seat_request.approved_at = timezone.now()
        seat_request.approved_by = admin_id
        seat_request.synced_to_sheets = False
        seat_request.save()

        serializer = self.get_serializer(seat_request)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a seat request"""
        seat_request = self.get_object()
        admin_id = request.data.get('admin_id')
        reason = request.data.get('reason', '')

        if not admin_id:
            return Response(
                {'error': 'admin_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        seat_request.status = 'Rejected'
        seat_request.approved_at = timezone.now()
        seat_request.approved_by = admin_id
        seat_request.rejection_reason = reason
        seat_request.synced_to_sheets = False
        seat_request.save()

        serializer = self.get_serializer(seat_request)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def settle(self, request, pk=None):
        """Settle a seat request - create deposit and mark as completed"""
        seat_request = self.get_object()
        admin_id = request.data.get('admin_id')
        payment_method = request.data.get('payment_method', 'Seat Payment')

        if not admin_id:
            return Response(
                {'error': 'admin_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if already settled
        if seat_request.status == 'Completed':
            return Response(
                {'error': 'Seat request already settled'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get account name from seat request (extracted from slip) or fallback
        account_name = seat_request.sender_account_name or 'Seat Payment'
        method = seat_request.payment_method or payment_method

        # Create a Deposit record for this seat payment
        deposit = Deposit.objects.create(
            user=seat_request.user,
            amount=seat_request.amount,
            method=method,
            account_name=account_name,
            proof_image_path=seat_request.slip_image_path,
            pppoker_id=seat_request.pppoker_id,
            status='Approved',
            approved_at=timezone.now(),
            approved_by=admin_id,
            synced_to_sheets=False
        )

        # Update user's account_name if this is their first deposit with a real name
        if account_name and account_name != 'Seat Payment' and not seat_request.user.account_name:
            seat_request.user.account_name = account_name
            seat_request.user.save()

        # Update user balance
        seat_request.user.balance += seat_request.amount
        seat_request.user.synced_to_sheets = False
        seat_request.user.save()

        # Mark seat request as completed
        seat_request.status = 'Completed'
        seat_request.synced_to_sheets = False
        seat_request.save()

        serializer = self.get_serializer(seat_request)
        return Response({
            'seat_request': serializer.data,
            'deposit_id': deposit.id
        })


class CashbackRequestViewSet(viewsets.ModelViewSet):
    """API endpoint for Cashback Requests"""
    queryset = CashbackRequest.objects.all()
    serializer_class = CashbackRequestSerializer

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending cashback requests"""
        cashbacks = CashbackRequest.objects.filter(status='Pending')
        serializer = self.get_serializer(cashbacks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def check_eligibility(self, request):
        """Check if user is eligible for cashback based on loss and minimum deposit"""
        from django.db.models import Sum
        from decimal import Decimal

        telegram_id = request.query_params.get('telegram_id')
        promotion_id = request.query_params.get('promotion_id')
        min_deposit = Decimal(request.query_params.get('min_deposit', '500'))

        if not telegram_id:
            return Response(
                {'error': 'telegram_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(telegram_id=int(telegram_id))
        except User.DoesNotExist:
            return Response(
                {'error': f'User not found with telegram_id: {telegram_id}'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError:
            return Response(
                {'error': f'Invalid telegram_id format: {telegram_id}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate total deposits (including all statuses for debugging)
        all_deposits_count = Deposit.objects.filter(user=user).count()
        approved_deposits_count = Deposit.objects.filter(user=user, status='Approved').count()

        total_deposits = Deposit.objects.filter(
            user=user,
            status='Approved'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # Calculate total withdrawals
        total_withdrawals = Withdrawal.objects.filter(
            user=user,
            status='Approved'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # Calculate total spin rewards (from approved spin history)
        total_spin_rewards = SpinHistory.objects.filter(
            user=user,
            status='Approved'
        ).aggregate(total=Sum('chips'))['total'] or Decimal('0')

        # Calculate total promotion bonuses
        total_bonuses = PromotionEligibility.objects.filter(
            user=user
        ).aggregate(total=Sum('bonus_amount'))['total'] or Decimal('0')

        # Calculate total cashback received
        total_cashback = CashbackEligibility.objects.filter(
            user=user
        ).aggregate(total=Sum('cashback_amount'))['total'] or Decimal('0')

        # Get last cashback claim for this promotion (if any)
        last_claim = None
        last_claim_deposits = Decimal('0')
        if promotion_id:
            last_claim = CashbackEligibility.objects.filter(
                user=user,
                promotion_id=promotion_id
            ).order_by('-received_at').first()

            if last_claim:
                # Get total deposits at time of last claim
                last_claim_deposits = Deposit.objects.filter(
                    user=user,
                    status='Approved',
                    created_at__lte=last_claim.received_at
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # Calculate effective new deposits (deposits since last claim)
        effective_new_deposits = total_deposits - last_claim_deposits

        # Calculate baseline (withdrawals + spin rewards + bonuses + cashback)
        baseline = total_withdrawals + total_spin_rewards + total_bonuses + total_cashback

        # Check if deposits exceed withdrawals (user is at a loss)
        deposits_exceed_withdrawals = total_deposits > baseline

        # Calculate club profit (baseline - deposits) and user loss
        club_profit = baseline - total_deposits
        user_loss = total_deposits - baseline

        # Check eligibility
        eligible = (
            deposits_exceed_withdrawals and  # User must be at a loss
            effective_new_deposits >= min_deposit  # Must meet minimum new deposit requirement
        )

        # Check if already claimed from this promotion
        already_claimed = False
        if promotion_id:
            already_claimed = CashbackEligibility.objects.filter(
                user=user,
                promotion_id=promotion_id
            ).exists()

        return Response({
            'eligible': eligible and not already_claimed,
            'current_deposits': float(total_deposits),
            'current_withdrawals': float(total_withdrawals),
            'total_spin_rewards': float(total_spin_rewards),
            'total_bonuses': float(total_bonuses),
            'total_cashback': float(total_cashback),
            'club_profit': float(club_profit),
            'user_loss': float(user_loss),
            'effective_new_deposits': float(effective_new_deposits),
            'last_claim_deposits': float(last_claim_deposits),
            'baseline': float(baseline),
            'min_required': float(min_deposit),
            'deposits_exceed_withdrawals': deposits_exceed_withdrawals,
            'already_claimed': already_claimed,
            # Debug info
            'debug_info': {
                'user_id': user.id,
                'user_telegram_id': user.telegram_id,
                'all_deposits_count': all_deposits_count,
                'approved_deposits_count': approved_deposits_count
            }
        })

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a cashback request"""
        from django.utils import timezone

        cashback_request = self.get_object()

        if cashback_request.status != 'Pending':
            return Response(
                {'error': f'Cashback request is already {cashback_request.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        approved_by = request.data.get('approved_by')
        if not approved_by:
            return Response(
                {'error': 'approved_by field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update cashback request
        cashback_request.status = 'Approved'
        cashback_request.approved_at = timezone.now()
        cashback_request.approved_by = approved_by
        cashback_request.save()

        # Update user balance
        user = cashback_request.user
        user.balance += cashback_request.cashback_amount
        user.save()

        # Create CashbackEligibility record to track this cashback was received
        # This prevents user from claiming again for the same promotion
        if cashback_request.promotion:
            CashbackEligibility.objects.create(
                user=user,
                promotion=cashback_request.promotion,
                cashback_request=cashback_request,
                loss_amount=cashback_request.investment_amount,
                cashback_amount=cashback_request.cashback_amount,
                notes=f'Cashback approved by admin {approved_by}'
            )

        serializer = self.get_serializer(cashback_request)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a cashback request"""
        from django.utils import timezone

        cashback_request = self.get_object()

        if cashback_request.status != 'Pending':
            return Response(
                {'error': f'Cashback request is already {cashback_request.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        rejection_reason = request.data.get('rejection_reason', 'No reason provided')
        approved_by = request.data.get('approved_by')

        # Update cashback request
        cashback_request.status = 'Rejected'
        cashback_request.approved_at = timezone.now()
        cashback_request.approved_by = approved_by
        cashback_request.rejection_reason = rejection_reason
        cashback_request.save()

        serializer = self.get_serializer(cashback_request)
        return Response(serializer.data)


class CashbackEligibilityViewSet(viewsets.ModelViewSet):
    """API endpoint for Cashback Eligibility"""
    queryset = CashbackEligibility.objects.all()
    serializer_class = CashbackEligibilitySerializer


class PaymentAccountViewSet(viewsets.ModelViewSet):
    """API endpoint for Payment Accounts"""
    queryset = PaymentAccount.objects.all()
    serializer_class = PaymentAccountSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active payment accounts"""
        accounts = PaymentAccount.objects.filter(is_active=True)
        serializer = self.get_serializer(accounts, many=True)
        return Response(serializer.data)


class AdminViewSet(viewsets.ModelViewSet):
    """API endpoint for Admins"""
    queryset = Admin.objects.all()
    serializer_class = AdminSerializer

    @action(detail=False, methods=['get'])
    def check(self, request):
        """Check if telegram_id is admin"""
        telegram_id = request.query_params.get('telegram_id')

        if not telegram_id:
            return Response(
                {'error': 'telegram_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_admin = Admin.objects.filter(
            telegram_id=telegram_id,
            is_active=True
        ).exists()

        return Response({'is_admin': is_admin})


class CounterStatusViewSet(viewsets.ModelViewSet):
    """API endpoint for Counter Status"""
    queryset = CounterStatus.objects.all()
    serializer_class = CounterStatusSerializer

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current counter status"""
        counter = CounterStatus.load()
        serializer = self.get_serializer(counter)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """Toggle counter open/close"""
        admin_id = request.data.get('admin_id', 0)

        try:
            counter = CounterStatus.load()
            counter.is_open = not counter.is_open
            counter.updated_by = admin_id
            counter.synced_to_sheets = False
            counter.save()

            serializer = self.get_serializer(counter)
            return Response(serializer.data)
        except Exception as e:
            import traceback
            return Response(
                {'error': str(e), 'traceback': traceback.format_exc()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PromoCodeViewSet(viewsets.ModelViewSet):
    """API endpoint for Promo Codes"""
    queryset = PromoCode.objects.all()
    serializer_class = PromoCodeSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active promo codes, optionally filtered by promo_type"""
        today = timezone.now().date()
        promos = PromoCode.objects.filter(
            is_active=True,
            start_date__lte=today,
            end_date__gte=today
        )

        # Filter by promo_type if provided
        promo_type = request.query_params.get('promo_type', None)
        if promo_type:
            promos = promos.filter(promo_type=promo_type)

        serializer = self.get_serializer(promos, many=True)
        return Response(serializer.data)


class PromotionEligibilityViewSet(viewsets.ModelViewSet):
    """API endpoint for Promotion Eligibility"""
    queryset = PromotionEligibility.objects.all()
    serializer_class = PromotionEligibilitySerializer

    @action(detail=False, methods=['get'])
    def check_eligibility(self, request):
        """Check if user is eligible for a promotion (hasn't received bonus from this promo yet)"""
        telegram_id = request.query_params.get('telegram_id')
        promotion_id = request.query_params.get('promotion_id')

        if not telegram_id or not promotion_id:
            return Response(
                {'error': 'telegram_id and promotion_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Check if user already received bonus from this promotion
            already_received = PromotionEligibility.objects.filter(
                user__telegram_id=telegram_id,
                promotion_id=promotion_id
            ).exists()

            return Response({'eligible': not already_received})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SupportMessageViewSet(viewsets.ModelViewSet):
    """API endpoint for Support Messages"""
    queryset = SupportMessage.objects.all()
    serializer_class = SupportMessageSerializer


class UserCreditViewSet(viewsets.ModelViewSet):
    """API endpoint for User Credits"""
    queryset = UserCredit.objects.all()
    serializer_class = UserCreditSerializer

    def get_queryset(self):
        """Filter credits by user telegram_id if provided"""
        queryset = UserCredit.objects.all()
        user_telegram_id = self.request.query_params.get('user', None)
        if user_telegram_id is not None:
            queryset = queryset.filter(user__telegram_id=user_telegram_id)
        return queryset


class ExchangeRateViewSet(viewsets.ModelViewSet):
    """API endpoint for Exchange Rates"""
    queryset = ExchangeRate.objects.all()
    serializer_class = ExchangeRateSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active exchange rates"""
        rates = ExchangeRate.objects.filter(is_active=True)
        serializer = self.get_serializer(rates, many=True)
        return Response(serializer.data)


class FiftyFiftyInvestmentViewSet(viewsets.ModelViewSet):
    """API endpoint for 50-50 Investments"""
    queryset = FiftyFiftyInvestment.objects.all()
    serializer_class = FiftyFiftyInvestmentSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active investments"""
        investments = FiftyFiftyInvestment.objects.filter(status='Active')
        serializer = self.get_serializer(investments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def mark_expired_as_lost(self, request):
        """Mark investments older than 24 hours as Lost"""
        from datetime import datetime, timedelta
        from django.utils import timezone as django_timezone

        try:
            # Calculate 24 hours ago from now
            cutoff_time = datetime.now().date() - timedelta(hours=24)

            # Find active investments older than 24 hours
            expired_investments = FiftyFiftyInvestment.objects.filter(
                status='Active',
                start_date__lt=cutoff_time
            )

            marked_count = 0
            today = datetime.now().date()

            for investment in expired_investments:
                # Mark as Lost
                # Loss share = full investment amount (club loses everything)
                investment.status = 'Lost'
                investment.loss_share = investment.investment_amount
                investment.profit_share = 0
                investment.end_date = today
                investment.save()
                marked_count += 1

            return Response({
                'success': True,
                'marked_count': marked_count,
                'message': f'Marked {marked_count} expired investments as Lost'
            })

        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClubBalanceViewSet(viewsets.ModelViewSet):
    """API endpoint for Club Balances"""
    queryset = ClubBalance.objects.all()
    serializer_class = ClubBalanceSerializer


class InventoryTransactionViewSet(viewsets.ModelViewSet):
    """API endpoint for Inventory Transactions"""
    queryset = InventoryTransaction.objects.all()
    serializer_class = InventoryTransactionSerializer


@api_view(['GET'])
def financial_report(request):
    """
    Generate financial reports with customizable date ranges
    Query params:
        - period: 'daily', 'weekly', 'monthly', '6months', 'yearly', 'custom'
        - start_date: YYYY-MM-DD (for custom period)
        - end_date: YYYY-MM-DD (for custom period)
    """
    from django.db.models import Sum, Count, Q
    from datetime import datetime, timedelta

    # Get period parameter
    period = request.query_params.get('period', 'daily')

    # Calculate date range based on period
    today = timezone.now().date()

    if period == 'custom':
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            return Response(
                {'error': 'start_date and end_date required for custom period'},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    elif period == 'daily':
        start_date = today
        end_date = today
    elif period == 'weekly':
        start_date = today - timedelta(days=7)
        end_date = today
    elif period == 'monthly':
        start_date = today - timedelta(days=30)
        end_date = today
    elif period == '6months':
        start_date = today - timedelta(days=180)
        end_date = today
    elif period == 'yearly':
        start_date = today - timedelta(days=365)
        end_date = today
    else:
        return Response(
            {'error': 'Invalid period. Use: daily, weekly, monthly, 6months, yearly, custom'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Convert to datetime for filtering
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))

    # === DEPOSITS ===
    deposits_data = Deposit.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_deposits=Sum('amount', filter=Q(status='Approved')) or 0,
        total_pending_deposits=Sum('amount', filter=Q(status='Pending')) or 0,
        approved_count=Count('id', filter=Q(status='Approved')),
        pending_count=Count('id', filter=Q(status='Pending')),
        rejected_count=Count('id', filter=Q(status='Rejected'))
    )

    # === WITHDRAWALS ===
    withdrawals_data = Withdrawal.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_withdrawals=Sum('amount', filter=Q(status='Approved')) or 0,
        total_pending_withdrawals=Sum('amount', filter=Q(status='Pending')) or 0,
        approved_count=Count('id', filter=Q(status='Approved')),
        pending_count=Count('id', filter=Q(status='Pending')),
        rejected_count=Count('id', filter=Q(status='Rejected'))
    )

    # === 50/50 INVESTMENTS ===
    investments_data = FiftyFiftyInvestment.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_investment=Sum('investment_amount') or 0,
        total_profit=Sum('profit_share') or 0,
        total_loss=Sum('loss_share') or 0,
        active_count=Count('id', filter=Q(status='Active')),
        completed_count=Count('id', filter=Q(status='Completed')),
        lost_count=Count('id', filter=Q(status='Lost'))
    )

    # Net investment profit/loss
    investment_net = (investments_data['total_profit'] or 0) - (investments_data['total_loss'] or 0)

    # === CASHBACK ===
    cashback_data = CashbackRequest.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_cashback=Sum('cashback_amount', filter=Q(status='Approved')) or 0,
        approved_count=Count('id', filter=Q(status='Approved')),
        pending_count=Count('id', filter=Q(status='Pending'))
    )

    # === SPIN REWARDS ===
    spin_data = SpinHistory.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_chips=Sum('chips', filter=Q(status='Approved')) or 0,
        total_spins=Count('id'),
        approved_count=Count('id', filter=Q(status='Approved')),
        pending_count=Count('id', filter=Q(status='Pending'))
    )

    # === USER CREDITS ===
    credits_data = UserCredit.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_credits=Sum('amount') or 0,
        count=Count('id')
    )

    # === USER GROWTH ===
    new_users = User.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).count()

    total_users = User.objects.count()

    # === INVENTORY ===
    inventory_data = InventoryTransaction.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_spent=Sum('total_amount', filter=Q(transaction_type='Add')) or 0,
        total_revenue=Sum('total_amount', filter=Q(transaction_type='Remove')) or 0
    )

    # === FINANCIAL SUMMARY ===
    total_income = (
        (deposits_data['total_deposits'] or 0) +
        (investments_data['total_profit'] or 0)
    )

    total_expenses = (
        (withdrawals_data['total_withdrawals'] or 0) +
        (cashback_data['total_cashback'] or 0) +
        (credits_data['total_credits'] or 0) +
        (investments_data['total_loss'] or 0)
    )

    net_profit = total_income - total_expenses

    # === COMPILE REPORT ===
    report = {
        'period': period,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'generated_at': timezone.now().isoformat(),

        'summary': {
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'net_profit': float(net_profit),
            'profit_margin': f"{(net_profit / total_income * 100) if total_income > 0 else 0:.2f}%"
        },

        'deposits': {
            'total_approved': float(deposits_data['total_deposits'] or 0),
            'total_pending': float(deposits_data['total_pending_deposits'] or 0),
            'approved_count': deposits_data['approved_count'],
            'pending_count': deposits_data['pending_count'],
            'rejected_count': deposits_data['rejected_count']
        },

        'withdrawals': {
            'total_approved': float(withdrawals_data['total_withdrawals'] or 0),
            'total_pending': float(withdrawals_data['total_pending_withdrawals'] or 0),
            'approved_count': withdrawals_data['approved_count'],
            'pending_count': withdrawals_data['pending_count'],
            'rejected_count': withdrawals_data['rejected_count']
        },

        'investments': {
            'total_investment': float(investments_data['total_investment'] or 0),
            'total_profit': float(investments_data['total_profit'] or 0),
            'total_loss': float(investments_data['total_loss'] or 0),
            'net_profit': float(investment_net),
            'active_count': investments_data['active_count'],
            'completed_count': investments_data['completed_count'],
            'lost_count': investments_data['lost_count']
        },

        'cashback': {
            'total_given': float(cashback_data['total_cashback'] or 0),
            'approved_count': cashback_data['approved_count'],
            'pending_count': cashback_data['pending_count']
        },

        'spin_rewards': {
            'total_chips_awarded': int(spin_data['total_chips'] or 0),
            'total_spins': spin_data['total_spins'],
            'approved_count': spin_data['approved_count'],
            'pending_count': spin_data['pending_count']
        },

        'user_credits': {
            'total_credits_given': float(credits_data['total_credits'] or 0),
            'count': credits_data['count']
        },

        'users': {
            'new_users': new_users,
            'total_users': total_users
        },

        'inventory': {
            'total_spent': float(inventory_data['total_spent'] or 0),
            'total_revenue': float(inventory_data['total_revenue'] or 0),
            'net': float((inventory_data['total_revenue'] or 0) - (inventory_data['total_spent'] or 0))
        }
    }

    return Response(report)


@api_view(['GET'])
def financial_report_dashboard(request):
    """
    HTML dashboard view for financial reports
    Provides a user-friendly interface with charts and export options
    """
    from django.shortcuts import render
    from django.db.models import Sum, Count, Q
    from datetime import datetime, timedelta
    from decimal import Decimal

    # Get period from query params
    period = request.GET.get('period', 'daily')
    custom_start = request.GET.get('start_date', '')
    custom_end = request.GET.get('end_date', '')

    # Calculate date range
    today = timezone.now().date()

    if period == 'custom' and custom_start and custom_end:
        try:
            start_date = datetime.strptime(custom_start, '%Y-%m-%d').date()
            end_date = datetime.strptime(custom_end, '%Y-%m-%d').date()
        except ValueError:
            start_date = today
            end_date = today
            period = 'daily'
    elif period == 'daily':
        start_date = today
        end_date = today
    elif period == 'weekly':
        start_date = today - timedelta(days=7)
        end_date = today
    elif period == 'monthly':
        start_date = today - timedelta(days=30)
        end_date = today
    elif period == '6months':
        start_date = today - timedelta(days=180)
        end_date = today
    elif period == 'yearly':
        start_date = today - timedelta(days=365)
        end_date = today
    else:
        start_date = today
        end_date = today
        period = 'daily'

    # Convert to datetime for filtering
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))

    # === COLLECT DATA ===

    # Deposits
    deposits_data = Deposit.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_deposits=Sum('amount', filter=Q(status='Approved')),
        total_pending_deposits=Sum('amount', filter=Q(status='Pending')),
        approved_count=Count('id', filter=Q(status='Approved')),
        pending_count=Count('id', filter=Q(status='Pending')),
        rejected_count=Count('id', filter=Q(status='Rejected'))
    )

    # Withdrawals
    withdrawals_data = Withdrawal.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_withdrawals=Sum('amount', filter=Q(status='Approved')),
        total_pending_withdrawals=Sum('amount', filter=Q(status='Pending')),
        approved_count=Count('id', filter=Q(status='Approved')),
        pending_count=Count('id', filter=Q(status='Pending')),
        rejected_count=Count('id', filter=Q(status='Rejected'))
    )

    # 50/50 Investments
    investments_data = FiftyFiftyInvestment.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_investment=Sum('investment_amount'),
        total_profit=Sum('profit_share'),
        total_loss=Sum('loss_share'),
        active_count=Count('id', filter=Q(status='Active')),
        completed_count=Count('id', filter=Q(status='Completed')),
        lost_count=Count('id', filter=Q(status='Lost'))
    )

    # Cashback
    cashback_data = CashbackRequest.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_cashback=Sum('cashback_amount', filter=Q(status='Approved')),
        approved_count=Count('id', filter=Q(status='Approved')),
        pending_count=Count('id', filter=Q(status='Pending'))
    )

    # Spin Rewards
    spin_data = SpinHistory.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_chips=Sum('chips', filter=Q(status='Approved')),
        total_spins=Count('id'),
        approved_count=Count('id', filter=Q(status='Approved')),
        pending_count=Count('id', filter=Q(status='Pending'))
    )

    # User Credits
    credits_data = UserCredit.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_credits=Sum('amount'),
        count=Count('id')
    )

    # User Growth
    new_users = User.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).count()

    total_users = User.objects.count()

    # Inventory
    inventory_data = InventoryTransaction.objects.filter(
        created_at__gte=start_datetime,
        created_at__lte=end_datetime
    ).aggregate(
        total_spent=Sum('total_amount', filter=Q(transaction_type='Add')),
        total_revenue=Sum('total_amount', filter=Q(transaction_type='Remove'))
    )

    # === CALCULATE FINANCIALS ===

    # Convert None to Decimal(0) for calculations
    def to_decimal(value):
        return Decimal(str(value)) if value else Decimal('0')

    total_deposits = to_decimal(deposits_data['total_deposits'])
    total_withdrawals = to_decimal(withdrawals_data['total_withdrawals'])
    total_investment_profit = to_decimal(investments_data['total_profit'])
    total_investment_loss = to_decimal(investments_data['total_loss'])
    total_cashback = to_decimal(cashback_data['total_cashback'])
    total_credits = to_decimal(credits_data['total_credits'])

    # Income = Deposits + Investment Profits
    total_income = total_deposits + total_investment_profit

    # Expenses = Withdrawals + Investment Losses + Cashback + Credits
    total_expenses = total_withdrawals + total_investment_loss + total_cashback + total_credits

    # Net Profit
    net_profit = total_income - total_expenses

    # Profit Margin
    profit_margin = (net_profit / total_income * 100) if total_income > 0 else Decimal('0')

    # Investment Net
    investment_net = total_investment_profit - total_investment_loss

    # === PREPARE CONTEXT ===
    context = {
        'title': 'Financial Reports Dashboard',
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'custom_start': custom_start,
        'custom_end': custom_end,

        # Summary
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'profit_margin': f"{profit_margin:.2f}",

        # Deposits
        'deposits_total': total_deposits,
        'deposits_pending': to_decimal(deposits_data['total_pending_deposits']),
        'deposits_approved_count': deposits_data['approved_count'],
        'deposits_pending_count': deposits_data['pending_count'],
        'deposits_rejected_count': deposits_data['rejected_count'],

        # Withdrawals
        'withdrawals_total': total_withdrawals,
        'withdrawals_pending': to_decimal(withdrawals_data['total_pending_withdrawals']),
        'withdrawals_approved_count': withdrawals_data['approved_count'],
        'withdrawals_pending_count': withdrawals_data['pending_count'],
        'withdrawals_rejected_count': withdrawals_data['rejected_count'],

        # Investments
        'investments_total': to_decimal(investments_data['total_investment']),
        'investments_profit': total_investment_profit,
        'investments_loss': total_investment_loss,
        'investments_net': investment_net,
        'investments_active': investments_data['active_count'],
        'investments_completed': investments_data['completed_count'],
        'investments_lost': investments_data['lost_count'],

        # Cashback
        'cashback_total': total_cashback,
        'cashback_approved_count': cashback_data['approved_count'],
        'cashback_pending_count': cashback_data['pending_count'],

        # Spin Rewards
        'spin_total_chips': spin_data['total_chips'] or 0,
        'spin_total_spins': spin_data['total_spins'],
        'spin_approved_count': spin_data['approved_count'],
        'spin_pending_count': spin_data['pending_count'],

        # User Credits
        'credits_total': total_credits,
        'credits_count': credits_data['count'],

        # Users
        'new_users': new_users,
        'total_users': total_users,

        # Inventory
        'inventory_spent': to_decimal(inventory_data['total_spent']),
        'inventory_revenue': to_decimal(inventory_data['total_revenue']),
        'inventory_net': to_decimal(inventory_data['total_revenue']) - to_decimal(inventory_data['total_spent']),
    }

    return render(request, 'reports/financial_dashboard.html', context)


@staff_member_required
def broadcast_page(request):
    """
    Admin page to broadcast messages to all users
    """
    return render(request, 'admin/broadcast.html')


@api_view(['POST'])
def broadcast_message(request):
    """
    API endpoint to broadcast a message to all users via Telegram bot
    Requires admin authentication
    """
    import requests
    import os
    import json

    # Get message from request
    message = request.data.get('message')
    photo_url = request.data.get('photo_url')  # Optional

    if not message and not photo_url:
        return Response(
            {'error': 'Message or photo_url is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get bot token from environment
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        return Response(
            {'error': 'Bot token not configured'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Get all user telegram IDs
    user_ids = list(User.objects.values_list('telegram_id', flat=True))

    if not user_ids:
        return Response(
            {'error': 'No users found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Send broadcast to bot
    success_count = 0
    failed_count = 0

    for user_id in user_ids:
        try:
            if photo_url:
                # Send photo with caption
                url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                data = {
                    'chat_id': user_id,
                    'photo': photo_url,
                    'caption': message,
                    'parse_mode': 'Markdown'
                }
            else:
                # Send text message
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                data = {
                    'chat_id': user_id,
                    'text': message,
                    'parse_mode': 'Markdown'
                }

            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 200:
                success_count += 1
            else:
                failed_count += 1

        except Exception as e:
            failed_count += 1
            continue

    return Response({
        'success': True,
        'total_users': len(user_ids),
        'success_count': success_count,
        'failed_count': failed_count,
        'message': f'Broadcast sent to {success_count} users'
    })


class NotificationMessageViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Notification Messages (Telegram message IDs for button removal)

    list: Get all notification messages
    retrieve: Get specific notification message
    create: Create new notification message
    destroy: Delete notification message
    get_by_key: Get all messages for a notification_key (custom action)
    delete_by_key: Delete all messages for a notification_key (custom action)
    """
    queryset = NotificationMessage.objects.all()
    serializer_class = NotificationMessageSerializer

    @action(detail=False, methods=['get'])
    def get_by_key(self, request):
        """Get all messages for a notification_key"""
        notification_key = request.query_params.get('notification_key')
        if not notification_key:
            return Response({'error': 'notification_key parameter required'}, status=status.HTTP_400_BAD_REQUEST)

        messages = NotificationMessage.objects.filter(notification_key=notification_key)
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['delete'])
    def delete_by_key(self, request):
        """Delete all messages for a notification_key"""
        notification_key = request.data.get('notification_key')
        if not notification_key:
            return Response({'error': 'notification_key required'}, status=status.HTTP_400_BAD_REQUEST)

        deleted_count = NotificationMessage.objects.filter(notification_key=notification_key).delete()[0]
        return Response({
            'success': True,
            'deleted_count': deleted_count,
            'notification_key': notification_key
        })
