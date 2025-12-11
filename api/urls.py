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
router.register(r'spin-awards', views.SpinAwardViewSet, basename='spinaward')
router.register(r'spin-usages', views.SpinUsageViewSet, basename='spinusage')
router.register(r'spin-history', views.SpinHistoryViewSet, basename='spinhistory')
router.register(r'join-requests', views.JoinRequestViewSet, basename='joinrequest')
router.register(r'seat-requests', views.SeatRequestViewSet, basename='seatrequest')
router.register(r'cashback-requests', views.CashbackRequestViewSet, basename='cashbackrequest')
router.register(r'cashback-eligibility', views.CashbackEligibilityViewSet, basename='cashbackeligibility')
router.register(r'payment-accounts', views.PaymentAccountViewSet, basename='paymentaccount')
router.register(r'admins', views.AdminViewSet, basename='admin')
router.register(r'counter-status', views.CounterStatusViewSet, basename='counterstatus')
router.register(r'promo-codes', views.PromoCodeViewSet, basename='promocode')
router.register(r'promotion-eligibility', views.PromotionEligibilityViewSet, basename='promotioneligibility')
router.register(r'support-messages', views.SupportMessageViewSet, basename='supportmessage')
router.register(r'user-credits', views.UserCreditViewSet, basename='usercredit')
router.register(r'exchange-rates', views.ExchangeRateViewSet, basename='exchangerate')
router.register(r'investments', views.FiftyFiftyInvestmentViewSet, basename='investment')
router.register(r'club-balances', views.ClubBalanceViewSet, basename='clubbalance')
router.register(r'inventory-transactions', views.InventoryTransactionViewSet, basename='inventorytransaction')
router.register(r'notification-messages', views.NotificationMessageViewSet, basename='notificationmessage')

urlpatterns = [
    path('', include(router.urls)),
    path('health/', views.health_check, name='health_check'),
    path('reports/financial/', views.financial_report, name='financial_report'),
    path('reports/dashboard/', views.financial_report_dashboard, name='financial_report_dashboard'),
]
