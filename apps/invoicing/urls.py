"""
URL routing for the ``invoicing`` app's Supplier Invoices (CPMAS-32) and
Client Invoices (CPMAS-35) APIs.

Mounted under /api/invoicing/ by construction/urls.py.
"""
from rest_framework.routers import DefaultRouter

from .views import (
    ClientInvoiceItemViewSet,
    ClientInvoiceViewSet,
    SupplierInvoiceItemViewSet,
    SupplierInvoiceViewSet,
)

router = DefaultRouter()
router.register('supplier-invoices', SupplierInvoiceViewSet, basename='supplierinvoice')
router.register('supplier-invoice-items', SupplierInvoiceItemViewSet, basename='supplierinvoiceitem')
router.register('client-invoices', ClientInvoiceViewSet, basename='clientinvoice')
router.register('client-invoice-items', ClientInvoiceItemViewSet, basename='clientinvoiceitem')

urlpatterns = router.urls
