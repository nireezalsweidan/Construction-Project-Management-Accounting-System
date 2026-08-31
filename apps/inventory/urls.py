"""
URL routing for the ``inventory`` app's API -- Material Management
(CPMAS-28) and Inventory & Warehouse Management (CPMAS-29) slices.

Mounted under /api/inventory/ by construction/urls.py. Uses a DRF
DefaultRouter so each viewset gets its standard routes (plus any
@action-decorated custom ones, e.g. stocks/low_stock/ and
stock-movements/transfer/) without hand-writing each path.
"""
from rest_framework.routers import DefaultRouter

from .views import (
    MaterialCategoryViewSet,
    MaterialViewSet,
    StockMovementViewSet,
    StockViewSet,
    WarehouseViewSet,
)

router = DefaultRouter()
router.register('material-categories', MaterialCategoryViewSet, basename='materialcategory')
router.register('materials', MaterialViewSet, basename='material')
router.register('warehouses', WarehouseViewSet, basename='warehouse')
router.register('stocks', StockViewSet, basename='stock')
router.register('stock-movements', StockMovementViewSet, basename='stockmovement')

urlpatterns = router.urls
