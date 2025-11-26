"""
Django Admin Configuration for Billionaires PPPoker Bot
Registers all models to the admin panel for easy management
"""

from django.contrib import admin
from .models import (
    User, Deposit, Withdrawal, SpinUser, SpinHistory,
    PaymentAccount, CounterStatus, Admin, JoinRequest,
    SeatRequest, CashbackRequest, PromoCode, SupportMessage,
    UserCredit, ExchangeRate, FiftyFiftyInvestment, ClubBalance,
    InventoryTransaction
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['telegram_id', 'username', 'pppoker_id', 'balance', 'club_balance', 'created_at']
    search_fields = ['telegram_id', 'username', 'pppoker_id']
    list_filter = ['created_at', 'synced_to_sheets']
    ordering = ['-created_at']


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'method', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'method', 'created_at']
    search_fields = ['user__username', 'user__telegram_id', 'account_number']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'method', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'method', 'created_at']
    search_fields = ['user__username', 'user__telegram_id', 'account_number']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(SpinUser)
class SpinUserAdmin(admin.ModelAdmin):
    list_display = ['telegram_id', 'username', 'available_spins', 'total_spins_used', 'total_chips_earned']
    search_fields = ['telegram_id', 'username', 'pppoker_id']
    list_filter = ['created_at']
    ordering = ['-total_chips_earned']


@admin.register(SpinHistory)
class SpinHistoryAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'username', 'prize', 'chips', 'status', 'timestamp', 'approved_by']
    list_filter = ['status', 'timestamp']
    search_fields = ['user_id', 'username', 'pppoker_id']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp', 'approved_at']


@admin.register(PaymentAccount)
class PaymentAccountAdmin(admin.ModelAdmin):
    list_display = ['method', 'account_name', 'account_number', 'is_active', 'updated_at']
    list_filter = ['method', 'is_active']
    search_fields = ['account_name', 'account_number']
    ordering = ['method']


@admin.register(CounterStatus)
class CounterStatusAdmin(admin.ModelAdmin):
    list_display = ['is_open', 'updated_by', 'updated_at']
    readonly_fields = ['updated_at']

    def has_add_permission(self, request):
        # Only allow one CounterStatus instance
        return not CounterStatus.objects.exists()


@admin.register(Admin)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ['admin_id', 'username', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['admin_id', 'username']
    ordering = ['-created_at']


@admin.register(JoinRequest)
class JoinRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'pppoker_id', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'pppoker_id']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(SeatRequest)
class SeatRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(CashbackRequest)
class CashbackRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'bonus_amount', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['code']
    ordering = ['-created_at']


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'message']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'resolved_at']


@admin.register(UserCredit)
class UserCreditAdmin(admin.ModelAdmin):
    list_display = ['user', 'credit_amount', 'updated_at']
    search_fields = ['user__username']
    ordering = ['-updated_at']


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['from_currency', 'to_currency', 'rate', 'updated_at']
    list_filter = ['from_currency', 'to_currency']
    ordering = ['-updated_at']


@admin.register(FiftyFiftyInvestment)
class FiftyFiftyInvestmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'investment_amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'settled_at']


@admin.register(ClubBalance)
class ClubBalanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'updated_at']
    search_fields = ['user__username']
    ordering = ['-updated_at']


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'transaction_type', 'amount', 'timestamp']
    list_filter = ['transaction_type', 'timestamp']
    search_fields = ['user__username', 'description']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp']
