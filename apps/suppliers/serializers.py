"""
DRF serializers for the ``suppliers`` app -- Supplier Management.

Reads supplier profile/contact/payment-terms from the managed ``Supplier``
model (db_table='suppliers') and exposes read-only views into the
supplier's purchase orders (``purchasing.PurchaseOrder``), supplier
invoices (``invoicing.SupplierInvoice``), payments (``clients.ClientPayment``
over the shared ``payments`` table), receipts (``ReceiptSummary`` over the
``receipts`` table), and the outstanding payable balance (computed by
``suppliers.models.get_supplier_financials``).

No new tables are created: every read-mostly source here already exists in
the approved Supabase schema (see suppliers/models.py docstring for the
receipts relationship).
"""
from clients.models import ClientPayment
from invoicing.models import SupplierInvoice
from purchasing.models import PurchaseOrder
from rest_framework import serializers

from .models import CURRENCY, ReceiptSummary, Supplier, get_supplier_financials


class SupplierListSerializer(serializers.ModelSerializer):
    """Thin representation for list views -- no computed balance per row."""

    class Meta:
        model = Supplier
        fields = ["id", "name", "company_name", "phone", "email", "tax_number", "is_active"]


class SupplierSerializer(serializers.ModelSerializer):
    """
    Full read/write representation.

    ``currency`` is the system-wide constant (USD) -- there is no stored
    per-supplier currency column in the schema.
    ``outstanding_balance`` is computed, not stored -- see
    ``get_supplier_financials``.
    """

    currency = serializers.SerializerMethodField()
    outstanding_balance = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "company_name",
            "phone",
            "email",
            "address",
            "tax_number",
            "payment_terms",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
            "currency",
            "outstanding_balance",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "currency", "outstanding_balance"]

    def get_currency(self, obj):
        return CURRENCY

    def get_outstanding_balance(self, obj):
        value = get_supplier_financials(obj.id)["outstanding_balance"]
        return f"{value:.2f}"


class SupplierPurchaseOrderSerializer(serializers.ModelSerializer):
    """Read-only header fields of a supplier's purchase orders."""

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "po_number",
            "order_date",
            "expected_delivery_date",
            "total_amount",
            "status",
        ]


class SupplierInvoiceSummarySerializer(serializers.ModelSerializer):
    """Read-only header fields of a supplier's invoices."""

    class Meta:
        model = SupplierInvoice
        fields = [
            "id",
            "invoice_number",
            "invoice_date",
            "due_date",
            "total_amount",
            "status",
        ]


class SupplierPaymentSerializer(serializers.ModelSerializer):
    """Read-only view of the supplier's outgoing payments."""

    class Meta:
        model = ClientPayment
        fields = [
            "id",
            "payment_number",
            "payment_date",
            "amount",
            "payment_method",
            "reference",
        ]


class SupplierReceiptSerializer(serializers.ModelSerializer):
    """Read-only view of receipts recorded against the supplier's payments."""

    class Meta:
        model = ReceiptSummary
        fields = [
            "id",
            "payment_id",
            "receipt_number",
            "receipt_date",
            "amount",
            "reference",
        ]


class SupplierBalanceSerializer(serializers.Serializer):
    """
    Shape of the /balance/ action response. Uses DecimalField (not a raw
    dict of Decimals) so monetary totals serialize as strings like the rest
    of the API, rather than DRF's float fallback for plain Decimal values.
    """

    supplier_id = serializers.UUIDField()
    currency = serializers.CharField()
    total_invoiced = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=18, decimal_places=2)
    outstanding_balance = serializers.DecimalField(max_digits=18, decimal_places=2)