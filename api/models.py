"""
Django Models for Billionaires PPPoker Bot
Complete database schema matching Google Sheets structure
"""

from django.db import models
from django.utils import timezone


class User(models.Model):
    """User model - matches Users sheet"""
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=255)
    pppoker_id = models.CharField(max_length=50, blank=True, default='')
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    club_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['telegram_id']),
            models.Index(fields=['synced_to_sheets']),
        ]

    def __str__(self):
        return f"{self.username} ({self.telegram_id})"


class Deposit(models.Model):
    """Deposit model - matches Deposits sheet"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposits')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    method = models.CharField(max_length=100)
    account_name = models.CharField(max_length=255)
    proof_image_path = models.CharField(max_length=500)
    pppoker_id = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.BigIntegerField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'deposits'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Deposit {self.id} - {self.user.username} - {self.amount} - {self.status}"


class Withdrawal(models.Model):
    """Withdrawal model - matches Withdrawals sheet"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    method = models.CharField(max_length=100)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=255)
    pppoker_id = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.BigIntegerField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'withdrawals'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Withdrawal {self.id} - {self.user.username} - {self.amount} - {self.status}"


class SpinUser(models.Model):
    """Spin User model - matches Spin_Users sheet"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='spin_data')
    available_spins = models.IntegerField(default=0)
    total_spins_used = models.IntegerField(default=0)
    total_chips_earned = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'spin_users'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['synced_to_sheets']),
        ]

    def __str__(self):
        return f"SpinUser {self.user.username} - {self.available_spins} spins"


class SpinHistory(models.Model):
    """Spin History model - matches Spin_History sheet"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Auto', 'Auto'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='spin_history')
    prize = models.CharField(max_length=100)
    chips = models.IntegerField()
    pppoker_id = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.BigIntegerField(null=True, blank=True)
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'spin_history'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Spin {self.id} - {self.user.username} - {self.prize} - {self.status}"


class JoinRequest(models.Model):
    """Join Request model - matches Join_Requests sheet"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='join_requests')
    pppoker_id = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.BigIntegerField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'join_requests'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Join {self.id} - {self.user.username} - {self.pppoker_id} - {self.status}"


class SeatRequest(models.Model):
    """Seat Request model - matches Seat_Requests sheet"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seat_requests')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    slip_image_path = models.CharField(max_length=500)
    pppoker_id = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.BigIntegerField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'seat_requests'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Seat {self.id} - {self.user.username} - {self.amount} - {self.status}"


class CashbackRequest(models.Model):
    """Cashback Request model - matches Cashback sheet"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cashback_requests')
    week_start = models.DateField()
    week_end = models.DateField()
    investment_amount = models.DecimalField(max_digits=15, decimal_places=2)
    cashback_amount = models.DecimalField(max_digits=15, decimal_places=2)
    cashback_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    pppoker_id = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.BigIntegerField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'cashback_requests'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['week_start', 'week_end']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Cashback {self.id} - {self.user.username} - {self.cashback_amount} - {self.status}"


class PaymentAccount(models.Model):
    """Payment Account model - matches Payment_Accounts sheet"""
    METHOD_CHOICES = [
        ('BTC', 'Bitcoin'),
        ('USDT_TRC20', 'USDT TRC20'),
        ('USDT_BEP20', 'USDT BEP20'),
        ('BankTransfer', 'Bank Transfer'),
    ]

    method = models.CharField(max_length=50, choices=METHOD_CHOICES, unique=True)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'payment_accounts'
        indexes = [
            models.Index(fields=['method', 'is_active']),
            models.Index(fields=['synced_to_sheets']),
        ]

    def __str__(self):
        return f"{self.method} - {self.account_name}"


class Admin(models.Model):
    """Admin model - matches Admins sheet"""
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=255)
    role = models.CharField(max_length=50, default='Admin')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'admins'
        indexes = [
            models.Index(fields=['telegram_id']),
            models.Index(fields=['is_active']),
            models.Index(fields=['synced_to_sheets']),
        ]

    def __str__(self):
        return f"Admin {self.username} ({self.telegram_id})"


class CounterStatus(models.Model):
    """Counter Status model - singleton for counter open/close status"""
    is_open = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.BigIntegerField()
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'counter_status'

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton pattern)
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # Prevent deletion

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1, defaults={'is_open': True, 'updated_by': 0})
        return obj

    def __str__(self):
        status = "OPEN" if self.is_open else "CLOSED"
        return f"Counter Status: {status}"


class PromoCode(models.Model):
    """Promo Code model - matches Promo sheet"""
    PROMO_TYPE_CHOICES = [
        ('bonus', 'Deposit Bonus'),
        ('cashback', 'Cashback'),
    ]

    code = models.CharField(max_length=50, unique=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    promo_type = models.CharField(max_length=20, choices=PROMO_TYPE_CHOICES, default='bonus')
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'promo_codes'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
            models.Index(fields=['promo_type', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['synced_to_sheets']),
        ]

    def __str__(self):
        return f"Promo {self.code} - {self.percentage}% ({self.get_promo_type_display()})"


class SupportMessage(models.Model):
    """Support Message model - for live chat support"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_messages')
    message = models.TextField()
    is_from_user = models.BooleanField(default=True)
    replied_by = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'support_messages'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['created_at']

    def __str__(self):
        msg_type = "User" if self.is_from_user else "Admin"
        return f"{msg_type} message from {self.user.username} at {self.created_at}"


class UserCredit(models.Model):
    """User Credit model - matches User Credits sheet"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credits')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    credit_type = models.CharField(max_length=100)  # Bonus, Refund, Adjustment, etc.
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.BigIntegerField()  # Admin who created it
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'user_credits'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Credit {self.id} - {self.user.username} - {self.amount} - {self.credit_type}"


class ExchangeRate(models.Model):
    """Exchange Rate model - matches Exchange Rates sheet"""
    currency_from = models.CharField(max_length=10)  # USD, BTC, USDT, etc.
    currency_to = models.CharField(max_length=10)  # USD, BTC, USDT, etc.
    rate = models.DecimalField(max_digits=20, decimal_places=8)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'exchange_rates'
        indexes = [
            models.Index(fields=['currency_from', 'currency_to', 'is_active']),
            models.Index(fields=['synced_to_sheets']),
        ]
        unique_together = ['currency_from', 'currency_to']

    def __str__(self):
        return f"{self.currency_from}/{self.currency_to} = {self.rate}"


class FiftyFiftyInvestment(models.Model):
    """50-50 Investment model - matches 50-50_Investments sheet"""
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investments')
    investment_amount = models.DecimalField(max_digits=15, decimal_places=2)
    profit_share = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    loss_share = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'fifty_fifty_investments'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Investment {self.id} - {self.user.username} - {self.investment_amount} - {self.status}"


class ClubBalance(models.Model):
    """Club Balance model - matches Club_Balances sheet"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='club_balances')
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    last_updated = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, default='')
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'club_balances'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['synced_to_sheets']),
        ]

    def __str__(self):
        return f"Club Balance - {self.user.username} - {self.balance}"


class InventoryTransaction(models.Model):
    """Inventory Transaction model - matches Inventory_Transactions sheet"""
    TRANSACTION_TYPE_CHOICES = [
        ('Add', 'Add'),
        ('Remove', 'Remove'),
        ('Adjustment', 'Adjustment'),
    ]

    item_name = models.CharField(max_length=255)
    quantity = models.IntegerField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    price_per_unit = models.DecimalField(max_digits=15, decimal_places=2)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.BigIntegerField()  # Admin who created it
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'inventory_transactions'
        indexes = [
            models.Index(fields=['item_name', 'created_at']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Inventory {self.id} - {self.item_name} - {self.transaction_type} - {self.quantity}"


class CashbackEligibility(models.Model):
    """Cashback Eligibility model - tracks which users received cashback from promotions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cashback_eligibility')
    promotion = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name='cashback_recipients')
    cashback_request = models.ForeignKey(CashbackRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='eligibility_records')
    loss_amount = models.DecimalField(max_digits=15, decimal_places=2)
    cashback_amount = models.DecimalField(max_digits=15, decimal_places=2)
    received_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default='')
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'cashback_eligibility'
        indexes = [
            models.Index(fields=['user', 'promotion']),
            models.Index(fields=['received_at']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['-received_at']

    def __str__(self):
        return f"Cashback {self.id} - {self.user.username} - {self.cashback_amount} from {self.promotion.code}"


class PromotionEligibility(models.Model):
    """Promotion Eligibility model - tracks which users received deposit bonuses from promotions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='promotion_eligibility')
    promotion = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name='bonus_recipients')
    deposit = models.ForeignKey(Deposit, on_delete=models.SET_NULL, null=True, blank=True, related_name='eligibility_records')
    deposit_amount = models.DecimalField(max_digits=15, decimal_places=2)
    bonus_amount = models.DecimalField(max_digits=15, decimal_places=2)
    received_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default='')
    synced_to_sheets = models.BooleanField(default=False)

    class Meta:
        db_table = 'promotion_eligibility'
        indexes = [
            models.Index(fields=['user', 'promotion']),
            models.Index(fields=['received_at']),
            models.Index(fields=['synced_to_sheets']),
        ]
        ordering = ['-received_at']

    def __str__(self):
        return f"Bonus {self.id} - {self.user.username} - {self.bonus_amount} from {self.promotion.code}"
