"""
URL routing for the ``payments`` app's Accounts Receivable & Accounts
Payable API (CPMAS-35).

Mounted under /api/payments/ by construction/urls.py.
"""
from rest_framework.routers import DefaultRouter

from .views import PaymentAllocationViewSet, PaymentViewSet, ReceiptViewSet

router = DefaultRouter()
router.register('payments', PaymentViewSet, basename='payment')
router.register('payment-allocations', PaymentAllocationViewSet, basename='paymentallocation')
router.register('receipts', ReceiptViewSet, basename='receipt')

urlpatterns = router.urls
