"""
Models for the ``suppliers`` app.

Provides the ``Supplier`` master record used by purchasing, materials,
supplier invoices, and payments throughout the system.

Built now, ahead of its own "Supplier Management" ticket, purely as a
foreign-key target for ``inventory.Material.default_supplier`` (CPMAS-28).
It already implements the full ``suppliers`` table from the approved
database schema (BRD 5.4 Supplier Management), so the owning ticket should
not need to modify this model's shape -- only add the CRUD API, purchase
history views, and outstanding-payable-balance logic around it.
"""
import uuid

from django.db import models
from django.db.models import Sum


class Supplier(models.Model):
    """
    A vendor the company purchases materials/services from.

    Fields follow the ``suppliers`` table in the approved database schema
    exactly.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    # Schema column name is "tax_number" (distinct from clients.tax_id) --
    # kept as-is for parity with the approved design.
    tax_number = models.CharField(max_length=100, blank=True, null=True)

    payment_terms = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # Soft-disable flag: inactive suppliers are hidden from new selection
    # (e.g. as a material's default supplier or on a new PO) without losing
    # their history on past purchase orders / invoices.
    is_active = models.BooleanField(default=True)

    # Audit timestamps. Present on the live database table (added there
    # ahead of this model); mirrored here so they're readable/writable
    # through the ORM instead of silently existing only at the DB layer.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suppliers'
        ordering = ['name']
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'

    def __str__(self):
        return self.name


# System-wide reporting/display currency. The approved schema has NO
# per-supplier currency column (only company_details.currency exists, and no
# currencies table is provisioned in construction_management_supabase.sql) --
# supplier amounts are fixed to USD everywhere, so this is a plain constant,
# not a stored field. Do NOT introduce a suppliers.currency column.
CURRENCY = "USD"


class ReceiptSummary(models.Model):
    """
    Read-mostly mapping onto the shared ``receipts`` table, scoped to what
    the supplier profile needs: a receipt is tied to a supplier only via the
    payments table (``receipts.payment_id -> payments.id``; receipts has no
    supplier_id of its own -- see line 54 of the schema). A supplier's
    receipts are therefore those whose payment belongs to that supplier.

    ``managed = False``: the table already exists in Supabase; full receipt
    create/print lifecycle belongs to the Payments module, not here. Mirrors
    the read-only mapping style of ``clients.PaymentAllocation``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_id = models.UUIDField()
    receipt_number = models.CharField(max_length=100, unique=True)
    receipt_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reference = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "receipts"
        ordering = ["-receipt_date"]

    def __str__(self):
        return self.receipt_number


def get_supplier_financials(supplier_id):
    """
    Supplier-side counterpart of ``clients.get_client_financials``: one
    shared calculation used by both the supplier detail serializer
    (outstanding_balance) and the /balance/ endpoint (full breakdown), so
    the logic only lives in one place.

    total_invoiced excludes DRAFT and CANCELLED supplier invoices -- those
    aren't real payables yet/anymore.
    total_paid is the sum actually allocated against those invoices via
    payment_allocations (not a raw SUM of payments.amount, since a single
    payment can be split across multiple invoices -- same reasoning as the
    client helper).
    outstanding_balance = total_invoiced - total_paid.

    Imports are kept local (not module-level) purely to avoid the app-import
    ordering hazard of a models module importing another app's models at
    bootstrap time (invoicing/clients both load after suppliers).
    """
    from decimal import Decimal

    from clients.models import PaymentAllocation
    from invoicing.models import SupplierInvoice

    invoice_qs = SupplierInvoice.objects.filter(supplier_id=supplier_id).exclude(
        status__in=[SupplierInvoice.Status.DRAFT, SupplierInvoice.Status.CANCELLED]
    )
    total_invoiced = invoice_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")

    total_paid = PaymentAllocation.objects.filter(
        supplier_invoice_id__in=invoice_qs.values_list("id", flat=True)
    ).aggregate(total=Sum("allocated_amount"))["total"] or Decimal("0.00")

    return {
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "outstanding_balance": total_invoiced - total_paid,
    }
