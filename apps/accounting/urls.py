"""
URL routing for the ``accounting`` app's Accounting / Financial
Transactions API (CPMAS-34).

Mounted under /api/accounting/ by construction/urls.py.
"""
from rest_framework.routers import DefaultRouter

from .views import AccountViewSet, FinancialTransactionViewSet, ReportViewSet, TransactionLineViewSet

router = DefaultRouter()
router.register('accounts', AccountViewSet, basename='account')
router.register('financial-transactions', FinancialTransactionViewSet, basename='financialtransaction')
router.register('transaction-lines', TransactionLineViewSet, basename='transactionline')
router.register('reports', ReportViewSet, basename='report')

urlpatterns = router.urls
