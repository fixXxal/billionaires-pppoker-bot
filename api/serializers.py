"""
Django REST Framework Serializers
Converts Django models to/from JSON for API endpoints
"""

from rest_framework import serializers
from .models import (
    User, Deposit, Withdrawal, SpinUser, SpinHistory,
    JoinRequest, SeatRequest, CashbackRequest, PaymentAccount,
    Admin, CounterStatus, PromoCode, SupportMessage,
    UserCredit, ExchangeRate, FiftyFiftyInvestment,
    ClubBalance, InventoryTransaction
)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""

    class Meta:
        model = User
        fields = [
            'id', 'telegram_id', 'username', 'pppoker_id',
            'balance', 'club_balance', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DepositSerializer(serializers.ModelSerializer):
    """Serializer for Deposit model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = Deposit
        fields = [
            'id', 'user', 'user_details', 'amount', 'method',
            'account_name', 'proof_image_path', 'pppoker_id',
            'status', 'created_at', 'approved_at', 'approved_by',
            'rejection_reason'
        ]
        read_only_fields = ['id', 'created_at', 'approved_at']


class WithdrawalSerializer(serializers.ModelSerializer):
    """Serializer for Withdrawal model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = Withdrawal
        fields = [
            'id', 'user', 'user_details', 'amount', 'method',
            'account_name', 'account_number', 'pppoker_id',
            'status', 'created_at', 'approved_at', 'approved_by',
            'rejection_reason'
        ]
        read_only_fields = ['id', 'created_at', 'approved_at']


class SpinUserSerializer(serializers.ModelSerializer):
    """Serializer for SpinUser model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = SpinUser
        fields = [
            'id', 'user', 'user_details', 'available_spins',
            'total_spins_used', 'total_chips_earned', 'updated_at'
        ]
        read_only_fields = ['id', 'updated_at']


class SpinHistorySerializer(serializers.ModelSerializer):
    """Serializer for SpinHistory model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = SpinHistory
        fields = [
            'id', 'user', 'user_details', 'prize', 'chips',
            'pppoker_id', 'status', 'created_at', 'approved_at',
            'approved_by'
        ]
        read_only_fields = ['id', 'created_at', 'approved_at']


class JoinRequestSerializer(serializers.ModelSerializer):
    """Serializer for JoinRequest model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = JoinRequest
        fields = [
            'id', 'user', 'user_details', 'pppoker_id', 'status',
            'created_at', 'approved_at', 'approved_by', 'rejection_reason'
        ]
        read_only_fields = ['id', 'created_at', 'approved_at']


class SeatRequestSerializer(serializers.ModelSerializer):
    """Serializer for SeatRequest model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = SeatRequest
        fields = [
            'id', 'user', 'user_details', 'amount', 'slip_image_path',
            'pppoker_id', 'status', 'created_at', 'approved_at',
            'approved_by', 'rejection_reason'
        ]
        read_only_fields = ['id', 'created_at', 'approved_at']


class CashbackRequestSerializer(serializers.ModelSerializer):
    """Serializer for CashbackRequest model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = CashbackRequest
        fields = [
            'id', 'user', 'user_details', 'week_start', 'week_end',
            'investment_amount', 'cashback_amount', 'cashback_percentage',
            'pppoker_id', 'status', 'created_at', 'approved_at',
            'approved_by', 'rejection_reason'
        ]
        read_only_fields = ['id', 'created_at', 'approved_at']


class PaymentAccountSerializer(serializers.ModelSerializer):
    """Serializer for PaymentAccount model"""

    class Meta:
        model = PaymentAccount
        fields = [
            'id', 'method', 'account_name', 'account_number',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AdminSerializer(serializers.ModelSerializer):
    """Serializer for Admin model"""

    class Meta:
        model = Admin
        fields = [
            'id', 'telegram_id', 'username', 'role',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class CounterStatusSerializer(serializers.ModelSerializer):
    """Serializer for CounterStatus model"""

    class Meta:
        model = CounterStatus
        fields = ['id', 'is_open', 'updated_at', 'updated_by']
        read_only_fields = ['id', 'updated_at']


class PromoCodeSerializer(serializers.ModelSerializer):
    """Serializer for PromoCode model"""

    class Meta:
        model = PromoCode
        fields = [
            'id', 'code', 'percentage', 'start_date', 'end_date',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SupportMessageSerializer(serializers.ModelSerializer):
    """Serializer for SupportMessage model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = SupportMessage
        fields = [
            'id', 'user', 'user_details', 'message', 'is_from_user',
            'replied_by', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class UserCreditSerializer(serializers.ModelSerializer):
    """Serializer for UserCredit model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = UserCredit
        fields = [
            'id', 'user', 'user_details', 'amount', 'credit_type',
            'description', 'created_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at']


class ExchangeRateSerializer(serializers.ModelSerializer):
    """Serializer for ExchangeRate model"""

    class Meta:
        model = ExchangeRate
        fields = [
            'id', 'currency_from', 'currency_to', 'rate',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FiftyFiftyInvestmentSerializer(serializers.ModelSerializer):
    """Serializer for FiftyFiftyInvestment model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = FiftyFiftyInvestment
        fields = [
            'id', 'user', 'user_details', 'investment_amount',
            'profit_share', 'loss_share', 'status', 'start_date',
            'end_date', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ClubBalanceSerializer(serializers.ModelSerializer):
    """Serializer for ClubBalance model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = ClubBalance
        fields = [
            'id', 'user', 'user_details', 'balance',
            'last_updated', 'notes'
        ]
        read_only_fields = ['id', 'last_updated']


class InventoryTransactionSerializer(serializers.ModelSerializer):
    """Serializer for InventoryTransaction model"""

    class Meta:
        model = InventoryTransaction
        fields = [
            'id', 'item_name', 'quantity', 'transaction_type',
            'price_per_unit', 'total_amount', 'notes',
            'created_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at']
