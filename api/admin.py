"""
Django Admin Configuration for Billionaires PPPoker Bot
Registers all models to the admin panel for easy management
"""

from django.contrib import admin
from .models import (
    User, Deposit, Withdrawal, SpinUser, SpinHistory,
    PaymentAccount, CounterStatus, Admin, ClubJoinRequest,
    ClubMember, ClubDeposit, ClubWithdrawal, Transaction,
    Notification, SystemLog, BotConfig, DepositSlip, WithdrawalProof
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


@admin.register(ClubJoinRequest)
class ClubJoinRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'pppoker_id', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'pppoker_id']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(ClubMember)
class ClubMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'pppoker_id', 'joined_at', 'is_active']
    list_filter = ['is_active', 'joined_at']
    search_fields = ['user__username', 'pppoker_id']
    ordering = ['-joined_at']


@admin.register(ClubDeposit)
class ClubDepositAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(ClubWithdrawal)
class ClubWithdrawalAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'transaction_type', 'amount', 'balance_type', 'timestamp']
    list_filter = ['transaction_type', 'balance_type', 'timestamp']
    search_fields = ['user__username', 'description']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'message_preview', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['user__username', 'message']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'log_type', 'message_preview', 'created_at']
    list_filter = ['log_type', 'created_at']
    search_fields = ['message', 'metadata']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

    def message_preview(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Message'


@admin.register(BotConfig)
class BotConfigAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_preview', 'updated_at']
    search_fields = ['key', 'value']
    ordering = ['key']
    readonly_fields = ['updated_at']

    def value_preview(self, obj):
        return obj.value[:50] + '...' if len(obj.value) > 50 else obj.value
    value_preview.short_description = 'Value'


@admin.register(DepositSlip)
class DepositSlipAdmin(admin.ModelAdmin):
    list_display = ['id', 'deposit', 'file_name', 'uploaded_at']
    search_fields = ['deposit__user__username', 'file_name']
    ordering = ['-uploaded_at']
    readonly_fields = ['uploaded_at']


@admin.register(WithdrawalProof)
class WithdrawalProofAdmin(admin.ModelAdmin):
    list_display = ['id', 'withdrawal', 'file_name', 'uploaded_at']
    search_fields = ['withdrawal__user__username', 'file_name']
    ordering = ['-uploaded_at']
    readonly_fields = ['uploaded_at']
