"""
URL routing for the ``invoicing`` app's Supplier Invoices API (CPMAS-32).

Mounted under /api/invoicing/ by construction/urls.py.
"""
from rest_framework.routers import DefaultRouter

from .views import SupplierInvoiceItemViewSet, SupplierInvoiceViewSet

router = DefaultRouter()
router.register('supplier-invoices', SupplierInvoiceViewSet, basename='supplierinvoice')
router.register('supplier-invoice-items', SupplierInvoiceItemViewSet, basename='supplierinvoiceitem')

urlpatterns = router.urls
