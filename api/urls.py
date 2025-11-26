"""
API URL Configuration
Routes for all API endpoints
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router and register viewsets
router = DefaultRouter()

router.register(r'users', views.UserViewSet, basename='user')
router.register(r'deposits', views.DepositViewSet, basename='deposit')
router.register(r'withdrawals', views.WithdrawalViewSet, basename='withdrawal')
router.register(r'spin-users', views.SpinUserViewSet, basename='spinuser')
router.register(r'spin-history', views.SpinHistoryViewSet, basename='spinhistory')
router.register(r'join-requests', views.JoinRequestViewSet, basename='joinrequest')
router.register(r'seat-requests', views.SeatRequestViewSet, basename='seatrequest')
router.register(r'cashback-requests', views.CashbackRequestViewSet, basename='cashbackrequest')
router.register(r'payment-accounts', views.PaymentAccountViewSet, basename='paymentaccount')
router.register(r'admins', views.AdminViewSet, basename='admin')
router.register(r'counter-status', views.CounterStatusViewSet, basename='counterstatus')
router.register(r'promo-codes', views.PromoCodeViewSet, basename='promocode')
router.register(r'support-messages', views.SupportMessageViewSet, basename='supportmessage')
router.register(r'user-credits', views.UserCreditViewSet, basename='usercredit')
router.register(r'exchange-rates', views.ExchangeRateViewSet, basename='exchangerate')
router.register(r'investments', views.FiftyFiftyInvestmentViewSet, basename='investment')
router.register(r'club-balances', views.ClubBalanceViewSet, basename='clubbalance')
router.register(r'inventory-transactions', views.InventoryTransactionViewSet, basename='inventorytransaction')

urlpatterns = [
    path('', include(router.urls)),
]
