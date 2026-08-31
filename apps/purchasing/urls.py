"""
URL routing for the ``purchasing`` app's Purchase Order Management API
(CPMAS-30).

Mounted under /api/purchasing/ by construction/urls.py.
"""
from rest_framework.routers import DefaultRouter

from .views import PurchaseOrderItemViewSet, PurchaseOrderViewSet

router = DefaultRouter()
router.register('purchase-orders', PurchaseOrderViewSet, basename='purchaseorder')
router.register('purchase-order-items', PurchaseOrderItemViewSet, basename='purchaseorderitem')

urlpatterns = router.urls
