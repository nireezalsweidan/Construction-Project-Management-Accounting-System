"""
URL routing for the ``expenses`` app's Expense Management API (CPMAS-33).

Mounted under /api/expenses/ by construction/urls.py.
"""
from rest_framework.routers import DefaultRouter

from .views import ExpenseCategoryViewSet, ExpenseViewSet

router = DefaultRouter()
router.register('expense-categories', ExpenseCategoryViewSet, basename='expensecategory')
router.register('expenses', ExpenseViewSet, basename='expense')

urlpatterns = router.urls
