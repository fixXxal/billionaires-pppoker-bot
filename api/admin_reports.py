"""
Custom Django Admin Reports
Provides financial reporting dashboard in Django Admin
"""

from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    User, Deposit, Withdrawal, FiftyFiftyInvestment,
    CashbackRequest, SpinHistory, UserCredit, InventoryTransaction
)


class FinancialReportsAdmin(admin.ModelAdmin):
    """
    Custom admin view for financial reports
    """

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """Override changelist view to show reports dashboard"""

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

        return render(request, 'admin/financial_reports.html', context)
