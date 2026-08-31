"""
URL routing for the ``purchasing`` app's API -- Purchase Order Management
(CPMAS-30) and Goods Receiving (CPMAS-31) slices.

Mounted under /api/purchasing/ by construction/urls.py.
"""
from rest_framework.routers import DefaultRouter

from .views import (
    GoodsReceiptItemViewSet,
    GoodsReceiptViewSet,
    PurchaseOrderItemViewSet,
    PurchaseOrderViewSet,
)

router = DefaultRouter()
router.register('purchase-orders', PurchaseOrderViewSet, basename='purchaseorder')
router.register('purchase-order-items', PurchaseOrderItemViewSet, basename='purchaseorderitem')
router.register('goods-receipts', GoodsReceiptViewSet, basename='goodsreceipt')
router.register('goods-receipt-items', GoodsReceiptItemViewSet, basename='goodsreceiptitem')

urlpatterns = router.urls
