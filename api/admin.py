"""
Django Admin Configuration for Billionaires PPPoker Bot
Registers all models to the admin panel for easy management
"""

from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from .models import (
    User, Deposit, Withdrawal, SpinUser, SpinHistory,
    PaymentAccount, CounterStatus, Admin, JoinRequest,
    SeatRequest, CashbackRequest, PromoCode, SupportMessage,
    UserCredit, ExchangeRate, FiftyFiftyInvestment, ClubBalance,
    InventoryTransaction, CashbackEligibility, PromotionEligibility
)
from .admin_reports import FinancialReportsAdmin


# Custom Admin Site to add Reports link
class BillionairesAdminSite(admin.AdminSite):
    site_header = "Billionaires PPPoker Admin"
    site_title = "Billionaires Admin"
    index_title = "Dashboard"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reports/financial/', self.admin_view(FinancialReportsAdmin(User, self).changelist_view), name='financial_reports'),
        ]
        return custom_urls + urls

# Replace default admin site
admin_site = BillionairesAdminSite(name='admin')

# Re-register default Django models
from django.contrib.auth.models import User as DjangoUser, Group
admin_site.register(DjangoUser, admin.ModelAdmin)
admin_site.register(Group, admin.ModelAdmin)


class UserAdmin(admin.ModelAdmin):
    list_display = ['telegram_id', 'username', 'pppoker_id', 'balance', 'club_balance', 'created_at']
    search_fields = ['telegram_id', 'username', 'pppoker_id']
    list_filter = ['created_at', 'synced_to_sheets']
    ordering = ['-created_at']

admin_site.register(User, UserAdmin)


class DepositAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'method', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'method', 'created_at']
    search_fields = ['user__username', 'user__telegram_id', 'account_number']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']

admin_site.register(Deposit, DepositAdmin)


class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'method', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'method', 'created_at']
    search_fields = ['user__username', 'user__telegram_id', 'account_number']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']

admin_site.register(Withdrawal, WithdrawalAdmin)


class SpinUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'available_spins', 'total_spins_used', 'total_chips_earned', 'updated_at']
    search_fields = ['user__username', 'user__telegram_id']
    list_filter = ['updated_at']
    ordering = ['-total_chips_earned']

admin_site.register(SpinUser, SpinUserAdmin)


class SpinHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'prize', 'chips', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'pppoker_id']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']

admin_site.register(SpinHistory, SpinHistoryAdmin)


class PaymentAccountAdmin(admin.ModelAdmin):
    list_display = ['method', 'account_name', 'account_number', 'is_active', 'updated_at']
    list_filter = ['method', 'is_active']
    search_fields = ['account_name', 'account_number']
    ordering = ['method']

admin_site.register(PaymentAccount, PaymentAccountAdmin)


class CounterStatusAdmin(admin.ModelAdmin):
    list_display = ['is_open', 'updated_by', 'updated_at']
    readonly_fields = ['updated_at']

    def has_add_permission(self, request):
        # Only allow one CounterStatus instance
        return not CounterStatus.objects.exists()

admin_site.register(CounterStatus, CounterStatusAdmin)


class AdminUserAdmin(admin.ModelAdmin):
    list_display = ['telegram_id', 'username', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['telegram_id', 'username']
    ordering = ['-created_at']

admin_site.register(Admin, AdminUserAdmin)


class JoinRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'pppoker_id', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'pppoker_id']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']

admin_site.register(JoinRequest, JoinRequestAdmin)


@admin.register(SeatRequest)
class SeatRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(CashbackRequest)
class CashbackRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'cashback_amount', 'status', 'created_at', 'approved_by']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'percentage', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['code']
    ordering = ['-created_at']


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'is_from_user', 'created_at']
    list_filter = ['is_from_user', 'created_at']
    search_fields = ['user__username', 'message']
    ordering = ['-created_at']
    readonly_fields = ['created_at']


@admin.register(UserCredit)
class UserCreditAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'credit_type', 'created_at']
    search_fields = ['user__username']
    ordering = ['-created_at']


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['currency_from', 'currency_to', 'rate', 'updated_at']
    list_filter = ['currency_from', 'currency_to']
    ordering = ['-updated_at']


@admin.register(FiftyFiftyInvestment)
class FiftyFiftyInvestmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'investment_amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at']


@admin.register(ClubBalance)
class ClubBalanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'last_updated']
    search_fields = ['user__username']
    ordering = ['-last_updated']


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'item_name', 'transaction_type', 'total_amount', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['item_name', 'notes']
    ordering = ['-created_at']
    readonly_fields = ['created_at']


@admin.register(CashbackEligibility)
class CashbackEligibilityAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'promotion', 'loss_amount', 'cashback_amount', 'received_at']
    list_filter = ['promotion', 'received_at']
    search_fields = ['user__username', 'user__telegram_id', 'promotion__code']
    ordering = ['-received_at']
    readonly_fields = ['received_at']


@admin.register(PromotionEligibility)
class PromotionEligibilityAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'promotion', 'deposit_amount', 'bonus_amount', 'received_at']
    list_filter = ['promotion', 'received_at']
    search_fields = ['user__username', 'user__telegram_id', 'promotion__code']
    ordering = ['-received_at']
    readonly_fields = ['received_at']
