"""
Views for the ``suppliers`` app -- Supplier Management API.

``SupplierViewSet`` gives authenticated users (Owner/Accountant, per the
existing DRF SessionAuthentication + IsAuthenticated setup) a CRUD surface
for the Supplier master record plus read-only detail actions onto the
supplier's financial activity: purchase orders, invoices, payments,
receipts, and the outstanding payable balance.

Suppliers themselves are pure data records -- they get no authentication,
no login, and no user role anywhere in this app.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Cross-app imports are safe here (views load lazily, long after the app
# registry is fully populated) and follow the existing precedent of
# clients/views.py importing projects.models at module level.
from clients.models import ClientPayment
from invoicing.models import SupplierInvoice
from purchasing.models import PurchaseOrder

from .models import CURRENCY, ReceiptSummary, Supplier, get_supplier_financials
from .serializers import (
    SupplierBalanceSerializer,
    SupplierInvoiceSummarySerializer,
    SupplierListSerializer,
    SupplierPaymentSerializer,
    SupplierPurchaseOrderSerializer,
    SupplierReceiptSerializer,
    SupplierSerializer,
)


class SupplierViewSet(viewsets.ModelViewSet):
    """
    /api/suppliers/suppliers/                    GET (list), POST (create)
    /api/suppliers/suppliers/{id}/               GET, PATCH, PUT, DELETE
    /api/suppliers/suppliers/{id}/purchase_orders/  GET -- the supplier's purchase orders
    /api/suppliers/suppliers/{id}/invoices/      GET -- supplier invoices
    /api/suppliers/suppliers/{id}/payments/      GET -- outgoing payments to the supplier
    /api/suppliers/suppliers/{id}/receipts/      GET -- receipts against those payments
    /api/suppliers/suppliers/{id}/balance/       GET -- invoiced / paid / outstanding breakdown
    """

    permission_classes = [IsAuthenticated]
    queryset = Supplier.objects.all()

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "company_name", "email", "tax_number"]
    ordering_fields = ["created_at", "name"]
    ordering = ["name"]

    def get_serializer_class(self):
        return SupplierListSerializer if self.action == "list" else SupplierSerializer

    @action(detail=True, methods=["get"])
    def purchase_orders(self, request, pk=None):
        supplier = self.get_object()
        qs = PurchaseOrder.objects.filter(supplier=supplier).order_by("-order_date")
        return Response(SupplierPurchaseOrderSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def invoices(self, request, pk=None):
        supplier = self.get_object()
        qs = SupplierInvoice.objects.filter(supplier=supplier).order_by("-invoice_date")
        return Response(SupplierInvoiceSummarySerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def payments(self, request, pk=None):
        supplier = self.get_object()
        # A supplier's payments are the OUTGOING rows on the shared payments
        # table that carry this supplier_id (see payments.direction's
        # INCOMING/OUTGOING CHECK in the schema). No supplier-specific
        # payment table exists -- or is created -- for this.
        qs = ClientPayment.objects.filter(supplier_id=supplier.id, direction="OUTGOING").order_by(
            "-payment_date"
        )
        return Response(SupplierPaymentSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def receipts(self, request, pk=None):
        supplier = self.get_object()
        # receipts has no supplier_id of its own -- it links to suppliers
        # only through payments (receipts.payment_id -> payments.id), so a
        # supplier's receipts are those on any of that supplier's payments.
        payment_ids = ClientPayment.objects.filter(supplier_id=supplier.id).values_list("id", flat=True)
        qs = ReceiptSummary.objects.filter(payment_id__in=payment_ids).order_by("-receipt_date")
        return Response(SupplierReceiptSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        supplier = self.get_object()
        payload = {"supplier_id": supplier.id, "currency": CURRENCY, **get_supplier_financials(supplier.id)}
        return Response(SupplierBalanceSerializer(payload).data)