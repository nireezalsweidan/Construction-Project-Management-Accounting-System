"""
Views for the ``suppliers`` app -- Supplier Management API.

``SupplierViewSet`` gives authenticated users (Owner/Accountant, per the
existing DRF SessionAuthentication + IsAuthenticated setup) a CRUD surface
for the Supplier master record plus read-only detail actions onto the
supplier's financial activity: purchase orders, invoices, outgoing
payments, and the outstanding payable balance.

Suppliers themselves are pure data records -- they get no authentication,
no login, and no user role anywhere in this app.
"""
from decimal import Decimal

from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Cross-app imports are safe here (views load lazily, long after the app
# registry is fully populated) and follow the existing precedent of
# clients/views.py importing projects.models at module level.
from invoicing.models import SupplierInvoice
from payments.models import Payment, PaymentAllocation
from purchasing.models import PurchaseOrder

from .models import CURRENCY, Supplier, get_supplier_financials
from .serializers import (
    SupplierBalanceSerializer,
    SupplierInvoiceSummarySerializer,
    SupplierListSerializer,
    SupplierPaymentSerializer,
    SupplierPurchaseOrderSerializer,
    SupplierSerializer,
)


class SupplierViewSet(viewsets.ModelViewSet):
    """
    /api/suppliers/suppliers/                    GET (list), POST (create)
    /api/suppliers/suppliers/summary/            GET -- aggregate page totals
    /api/suppliers/suppliers/{id}/               GET, PATCH, PUT, DELETE
    /api/suppliers/suppliers/{id}/purchase_orders/  GET -- the supplier's purchase orders
    /api/suppliers/suppliers/{id}/invoices/      GET -- supplier invoices
    /api/suppliers/suppliers/{id}/payments/      GET -- outgoing payments to the supplier
    /api/suppliers/suppliers/{id}/balance/       GET -- invoiced / paid / outstanding breakdown
    """

    permission_classes = [IsAuthenticated]
    queryset = Supplier.objects.all()

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "company_name", "email", "tax_number"]
    ordering_fields = ["created_at", "name"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() in ("true", "1"))

        return queryset

    def get_serializer_class(self):
        return SupplierListSerializer if self.action == "list" else SupplierSerializer

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """Aggregate page totals for the dashboard: supplier counts plus the
        whole-portfolio invoicing / outgoing-payment activity (draft and
        cancelled invoices excluded, matching get_supplier_financials)."""
        invoice_qs = SupplierInvoice.objects.exclude(
            status__in=[SupplierInvoice.Status.DRAFT, SupplierInvoice.Status.CANCELLED]
        )
        total_invoiced = invoice_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
        total_paid = PaymentAllocation.objects.filter(
            supplier_invoice_id__in=invoice_qs.values_list("id", flat=True)
        ).aggregate(total=Sum("allocated_amount"))["total"] or Decimal("0.00")
        return Response({
            "currency": CURRENCY,
            "total_suppliers": Supplier.objects.count(),
            "active_suppliers": Supplier.objects.filter(is_active=True).count(),
            "total_invoiced": f"{total_invoiced:.2f}",
            "total_paid": f"{total_paid:.2f}",
            "outstanding_balance": f"{total_invoiced - total_paid:.2f}",
        })

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
        # table that carry this supplier (payments.direction's
        # INCOMING/OUTGOING CHECK in the schema). No supplier-specific
        # payment table exists -- or is created -- for this.
        qs = Payment.objects.filter(supplier=supplier, direction=Payment.Direction.OUTGOING).order_by(
            "-payment_date"
        )
        return Response(SupplierPaymentSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        supplier = self.get_object()
        payload = {"supplier_id": supplier.id, "currency": CURRENCY, **get_supplier_financials(supplier.id)}
        return Response(SupplierBalanceSerializer(payload).data)