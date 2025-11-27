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

from .models import (
    User, Deposit, Withdrawal, SpinUser, SpinHistory,
    JoinRequest, SeatRequest, CashbackRequest, PaymentAccount,
    Admin, CounterStatus, PromoCode, SupportMessage,
    UserCredit, ExchangeRate, FiftyFiftyInvestment,
    ClubBalance, InventoryTransaction
)
from .serializers import (
    UserSerializer, DepositSerializer, WithdrawalSerializer,
    SpinUserSerializer, SpinHistorySerializer, JoinRequestSerializer,
    SeatRequestSerializer, CashbackRequestSerializer, PaymentAccountSerializer,
    AdminSerializer, CounterStatusSerializer, PromoCodeSerializer,
    SupportMessageSerializer, UserCreditSerializer, ExchangeRateSerializer,
    FiftyFiftyInvestmentSerializer, ClubBalanceSerializer,
    InventoryTransactionSerializer
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
            # Get or create user
            user, created = User.objects.get_or_create(
                telegram_id=telegram_id,
                defaults={
                    'username': request.data.get('username', f'User{telegram_id}'),
                    'pppoker_id': request.data.get('pppoker_id', ''),
                }
            )
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

        # Update user balance
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


class SpinHistoryViewSet(viewsets.ModelViewSet):
    """API endpoint for Spin History"""
    queryset = SpinHistory.objects.all()
    serializer_class = SpinHistorySerializer

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending spin rewards"""
        spins = SpinHistory.objects.filter(status='Pending')
        serializer = self.get_serializer(spins, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def process_spin(self, request):
        """Process one or more spins"""
        telegram_id = request.data.get('telegram_id')
        spin_count = request.data.get('spin_count', 1)
        results = request.data.get('results', [])

        if not telegram_id:
            return Response(
                {'error': 'telegram_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(telegram_id=telegram_id)
            spin_user = SpinUser.objects.get(user=user)
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
        admin_id = request.data.get('admin_id')

        if not admin_id:
            return Response(
                {'error': 'admin_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        counter = CounterStatus.load()
        counter.is_open = not counter.is_open
        counter.updated_by = admin_id
        counter.synced_to_sheets = False
        counter.save()

        serializer = self.get_serializer(counter)
        return Response(serializer.data)


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


class SupportMessageViewSet(viewsets.ModelViewSet):
    """API endpoint for Support Messages"""
    queryset = SupportMessage.objects.all()
    serializer_class = SupportMessageSerializer


class UserCreditViewSet(viewsets.ModelViewSet):
    """API endpoint for User Credits"""
    queryset = UserCredit.objects.all()
    serializer_class = UserCreditSerializer


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


class ClubBalanceViewSet(viewsets.ModelViewSet):
    """API endpoint for Club Balances"""
    queryset = ClubBalance.objects.all()
    serializer_class = ClubBalanceSerializer


class InventoryTransactionViewSet(viewsets.ModelViewSet):
    """API endpoint for Inventory Transactions"""
    queryset = InventoryTransaction.objects.all()
    serializer_class = InventoryTransactionSerializer
