"""
Models for the ``purchasing`` app -- Purchase Order Management slice
(CPMAS-30).

Implements ``PurchaseOrder`` and ``PurchaseOrderItem``, matching the
``purchase_orders`` / ``purchase_order_items`` tables in the approved
schema (BRD 5.14 Purchase Order Management).

Line-item and header monetary totals (tax_amount, total_amount, subtotal)
are treated as derived values, computed by ``purchasing.services`` from
quantity/unit_price/tax_rate -- never accepted as direct API input. This
mirrors how ``inventory.Stock.quantity`` is derived-only elsewhere in this
codebase: the schema's own design notes say balances/totals should be
calculated from transactional data, not manually maintained.

``PurchaseOrder.project`` is intentionally NOT modeled -- same reasoning
as ``inventory.StockMovement.project`` (CPMAS-29): it's an optional FK
into ``projects.Project``, owned by a separate, currently-unbuilt ticket
(CPMAS-47). Adding it later is an additive migration.

Also implements ``GoodsReceipt`` / ``GoodsReceiptItem`` (CPMAS-31: Goods
Receiving), matching the ``goods_receipts`` / ``goods_receipt_items``
tables. Receiving is the point where a PO's ordered quantities turn into
actual on-hand stock -- see ``purchasing.services.receive_goods`` for how
a receipt's items, the resulting ``inventory.StockMovement`` rows, and
the parent PO's status all update together atomically.

``GoodsReceipt.received_by`` is intentionally NOT modeled -- it's an
optional FK into ``employees.Employee``, owned by a separate,
currently-unbuilt ticket (CPMAS-38), same reasoning as ``project`` above.
"""
import uuid

from django.db import models


class PurchaseOrder(models.Model):
    """
    A purchase order issued to a supplier.

    Matches the ``purchase_orders`` table. ``status`` values match the
    live Postgres enum ``po_status_enum`` exactly. Status is only ever
    changed through ``purchasing.services.transition_status`` (called from
    the submit/approve/cancel API actions) -- see the module docstring on
    ``purchasing.services`` for why a raw status PATCH isn't exposed.
    """

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        APPROVED = 'APPROVED', 'Approved'
        PARTIALLY_RECEIVED = 'PARTIALLY_RECEIVED', 'Partially Received'
        RECEIVED = 'RECEIVED', 'Received'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT: a supplier with purchase order history shouldn't be
    # deletable out from under it -- deactivate (is_active=False) instead.
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.PROTECT, related_name='purchase_orders')

    po_number = models.CharField(max_length=100, unique=True)
    order_date = models.DateField()
    expected_delivery_date = models.DateField(blank=True, null=True)

    # Derived from line items by purchasing.services.recalculate_po_totals
    # -- default=0 matches the live DB column default, used only for a
    # brand-new PO with no items yet.
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    # PROTECT: who created a PO is part of its audit trail and shouldn't
    # be erasable by deleting their user record. db_column='created_by':
    # unlike most FKs in this schema (supplier_id, material_id, ...), the
    # live column is literally named created_by with no _id suffix --
    # Django's default naming would otherwise look for created_by_id.
    created_by = models.ForeignKey(
        'users.User', on_delete=models.PROTECT, related_name='purchase_orders_created',
        db_column='created_by',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'purchase_orders'
        ordering = ['-order_date', '-created_at']
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'

    def __str__(self):
        return self.po_number


class PurchaseOrderItem(models.Model):
    """
    A single line item on a purchase order.

    Matches the ``purchase_order_items`` table. ``tax_amount`` and
    ``total_amount`` are derived by
    ``purchasing.services.compute_item_amounts`` from
    quantity/unit_price/tax_rate, not accepted as direct input.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # CASCADE matches the live database's FK constraint exactly
    # (purchase_order_items_purchase_order_id_fkey ... ON DELETE CASCADE):
    # deleting a PO deletes its line items with it, since a PO without any
    # of its own items is a data-integrity nonsense state, not something
    # to protect against by blocking the delete.
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')

    # PROTECT: a material referenced by an existing PO line shouldn't be
    # deletable out from under it.
    material = models.ForeignKey('inventory.Material', on_delete=models.PROTECT, related_name='purchase_order_items')

    description = models.TextField(blank=True, null=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)

    # SET_NULL: losing a tax rate shouldn't delete/block existing PO
    # lines -- same reasoning as Material.tax_rate in CPMAS-28.
    tax_rate = models.ForeignKey('taxes.TaxRate', on_delete=models.SET_NULL, blank=True, null=True, related_name='purchase_order_items')

    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        db_table = 'purchase_order_items'
        # No natural ordering column in the schema; ordering by id keeps
        # API pagination deterministic (an unordered queryset can return
        # inconsistent pages/duplicates/gaps across requests -- Django
        # warns about exactly this on any paginated, order-less queryset).
        ordering = ['id']
        verbose_name = 'Purchase Order Item'
        verbose_name_plural = 'Purchase Order Items'

    def __str__(self):
        return f"{self.material} x{self.quantity} on {self.purchase_order.po_number}"


class GoodsReceipt(models.Model):
    """
    A record of materials physically received against a purchase order.

    Matches the ``goods_receipts`` table. No ``updated_at`` (matches the
    live DB exactly) -- like ``StockMovement``, a receipt is an immutable
    ledger entry once created (see ``GoodsReceiptViewSet``): correcting a
    mis-receipt means recording an inventory ADJUSTMENT, not editing this
    row after the fact.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT: a PO with receiving history shouldn't be deletable out
    # from under it.
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='goods_receipts')

    receipt_number = models.CharField(max_length=100, unique=True)
    received_date = models.DateField()

    # PROTECT: a warehouse with receiving history shouldn't be deletable
    # out from under it -- deactivate (is_active=False) instead.
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.PROTECT, related_name='goods_receipts')

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'goods_receipts'
        ordering = ['-received_date', '-created_at']
        verbose_name = 'Goods Receipt'
        verbose_name_plural = 'Goods Receipts'

    def __str__(self):
        return self.receipt_number


class GoodsReceiptItem(models.Model):
    """
    A single line on a goods receipt: how much of one PO line was
    received in this shipment.

    Matches the ``goods_receipt_items`` table. ``quantity_received`` is
    validated against the linked PO item's remaining (ordered minus
    already received elsewhere) quantity by
    ``purchasing.services.receive_goods`` -- never accepted without that
    check, since over-receiving would silently corrupt both the PO's
    Ordered/Received/Remaining comparison (BRD 5.15) and the resulting
    stock movement.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # CASCADE matches the live database's FK constraint: deleting a
    # receipt deletes its line items with it (same reasoning as
    # PurchaseOrderItem.purchase_order above).
    goods_receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name='items')

    # PROTECT: a PO item with receiving history shouldn't be deletable
    # out from under it -- and since PurchaseOrderItem itself only allows
    # edits while its PO is DRAFT (before any receiving could exist),
    # this should never actually be exercised in practice.
    purchase_order_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.PROTECT, related_name='goods_receipt_items')

    quantity_received = models.DecimalField(max_digits=18, decimal_places=3)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'goods_receipt_items'
        # See PurchaseOrderItem.Meta.ordering -- same reasoning.
        ordering = ['id']
        verbose_name = 'Goods Receipt Item'
        verbose_name_plural = 'Goods Receipt Items'

    def __str__(self):
        return f"{self.quantity_received} of {self.purchase_order_item} on {self.goods_receipt.receipt_number}"
