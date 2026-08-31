"""
Models for the ``invoicing`` app -- Supplier Invoices slice (CPMAS-32).

Implements ``SupplierInvoice`` and ``SupplierInvoiceItem``, matching the
``supplier_invoices`` / ``supplier_invoice_items`` tables in the approved
schema (BRD 5.16 Supplier Invoices).

Line-item and header monetary totals follow the same derived-value
pattern as ``purchasing.PurchaseOrder``/``PurchaseOrderItem`` (CPMAS-30):
computed by ``invoicing.services``, never accepted as direct API input
for the header. Unlike PO items, ``SupplierInvoiceItem.quantity``/
``unit_price`` are nullable in the schema -- a line can be a flat charge
(e.g. a service fee) with nothing to multiply -- so the derivation rule
is slightly different; see ``invoicing.services.compute_item_amounts``.

``SupplierInvoice.status`` matches the live Postgres enum
``invoice_status_enum`` (DRAFT, SENT, PARTIALLY_PAID, PAID, OVERDUE,
CANCELLED) exactly. Only DRAFT/SENT/CANCELLED are reachable from this
ticket -- PARTIALLY_PAID/PAID/OVERDUE depend on payment allocations,
which don't exist yet (the Payments app is unbuilt). Same pattern as
CPMAS-30 originally leaving PurchaseOrder.RECEIVED unreachable until
CPMAS-31's goods receiving filled it in.
"""
import uuid

from django.db import models


class SupplierInvoice(models.Model):
    """
    An invoice received from a supplier, optionally tied to the
    purchase order it bills against.

    Matches the ``supplier_invoices`` table. Has no ``created_by`` column
    in the schema (unlike PurchaseOrder), so unlike that model there's no
    users.User dependency here at all.
    """

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SENT = 'SENT', 'Sent'
        PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
        PAID = 'PAID', 'Paid'
        OVERDUE = 'OVERDUE', 'Overdue'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT: a supplier with invoice history shouldn't be deletable out
    # from under it -- deactivate (is_active=False) instead.
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.PROTECT, related_name='supplier_invoices')

    # PROTECT (not SET_NULL): the PO/goods-receipt/invoice three-way match
    # is exactly the kind of audit trail that shouldn't silently go null
    # if the PO is deleted -- also matches the live DB's plain REFERENCES
    # with no ON DELETE clause (defaults to NO ACTION, i.e. blocks the
    # delete), unlike Material.tax_rate/default_supplier elsewhere in
    # this codebase, which really are meant to gracefully null out.
    purchase_order = models.ForeignKey(
        'purchasing.PurchaseOrder', on_delete=models.PROTECT, blank=True, null=True,
        related_name='supplier_invoices',
    )

    invoice_number = models.CharField(max_length=100, unique=True)
    invoice_date = models.DateField()
    due_date = models.DateField(blank=True, null=True)

    # Derived from line items by invoicing.services.recalculate_invoice_totals.
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'supplier_invoices'
        ordering = ['-invoice_date', '-created_at']
        verbose_name = 'Supplier Invoice'
        verbose_name_plural = 'Supplier Invoices'

    def __str__(self):
        return self.invoice_number


class SupplierInvoiceItem(models.Model):
    """
    A single line on a supplier invoice.

    Matches the ``supplier_invoice_items`` table. ``quantity``/
    ``unit_price`` are nullable (unlike PurchaseOrderItem's, which are
    required) -- a line can be a flat charge with no quantity/price
    breakdown, e.g. a delivery fee or service charge. See
    ``invoicing.services.compute_item_amounts`` for how tax_amount/
    total_amount are derived in each case.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # CASCADE matches the live database's FK constraint exactly.
    supplier_invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name='items')

    # SET_NULL: optional in the schema -- a flat-charge line (e.g. a
    # delivery fee) may not reference any material at all.
    material = models.ForeignKey('inventory.Material', on_delete=models.SET_NULL, blank=True, null=True, related_name='supplier_invoice_items')

    description = models.TextField()
    quantity = models.DecimalField(max_digits=18, decimal_places=3, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, blank=True, null=True)

    # SET_NULL: same reasoning as Material.tax_rate elsewhere in this codebase.
    tax_rate = models.ForeignKey('taxes.TaxRate', on_delete=models.SET_NULL, blank=True, null=True, related_name='supplier_invoice_items')

    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        db_table = 'supplier_invoice_items'
        # No natural ordering column in the schema -- see the same note
        # on purchasing.PurchaseOrderItem.Meta.ordering.
        ordering = ['id']
        verbose_name = 'Supplier Invoice Item'
        verbose_name_plural = 'Supplier Invoice Items'

    def __str__(self):
        return f"{self.description} on {self.supplier_invoice.invoice_number}"
