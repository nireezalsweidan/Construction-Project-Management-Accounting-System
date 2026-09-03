"""
Business logic for the ``purchasing`` app that must not live in a
serializer or viewset.

Three concerns are centralized here, each for the same reason
``inventory.services.apply_stock_movement`` exists: making a business
rule a single, explicitly-called function instead of scattered
serializer/view logic means it can't be silently bypassed by a future
code path.

1. Monetary totals (PurchaseOrderItem.tax_amount/total_amount,
   PurchaseOrder.subtotal/tax_amount/total_amount) are always computed
   here from quantity/unit_price/tax_rate -- never accepted as direct
   API input.
2. PurchaseOrder.status only ever changes through ``transition_status``
   (user-driven: submit/approve/cancel), which validates the transition
   against ``ALLOWED_TRANSITIONS`` -- never a raw field assignment -- so
   a client can't jump e.g. straight from DRAFT to RECEIVED without ever
   being APPROVED.
3. ``receive_goods`` (CPMAS-31) is the *system*-driven counterpart: it
   moves a PO to PARTIALLY_RECEIVED/RECEIVED based on what's actually
   been received, bypassing transition_status's user-facing allow-list
   entirely (those two states aren't reachable through it -- see
   ALLOWED_TRANSITIONS below), and is the single place PO items' received
   quantities are validated against what was actually ordered.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from inventory.models import StockMovement
from inventory.services import apply_stock_movement

from .models import GoodsReceipt, GoodsReceiptItem, PurchaseOrder, PurchaseOrderItem

TWO_PLACES = Decimal('0.01')


def compute_item_amounts(item: PurchaseOrderItem) -> PurchaseOrderItem:
    """
    Set tax_amount and total_amount on a (not-yet-saved) PurchaseOrderItem
    from its quantity, unit_price, and tax_rate. Does not save -- callers
    save once after calling this, so it composes cleanly with
    recalculate_po_totals's own save.
    """
    line_subtotal = (item.quantity * item.unit_price).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    if item.tax_rate_id and item.tax_rate:
        tax_amount = (line_subtotal * item.tax_rate.rate / Decimal('100')).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    else:
        tax_amount = Decimal('0.00')

    item.tax_amount = tax_amount
    item.total_amount = line_subtotal + tax_amount
    return item


@transaction.atomic
def recalculate_po_totals(purchase_order: PurchaseOrder) -> PurchaseOrder:
    """
    Recompute a PurchaseOrder's subtotal/tax_amount/total_amount from the
    current sum of its line items' (quantity*unit_price)/tax_amount/
    total_amount. Called after any item create/update/delete.
    """
    items = purchase_order.items.all()

    line_subtotal_sum = sum(
        (i.quantity * i.unit_price for i in items), Decimal('0.00')
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    tax_sum = sum((i.tax_amount for i in items), Decimal('0.00'))
    total_sum = sum((i.total_amount for i in items), Decimal('0.00'))

    purchase_order.subtotal = line_subtotal_sum
    purchase_order.tax_amount = tax_sum
    purchase_order.total_amount = total_sum
    purchase_order.save(update_fields=['subtotal', 'tax_amount', 'total_amount', 'updated_at'])
    return purchase_order


# Explicit allow-list of valid status transitions. RECEIVED/
# PARTIALLY_RECEIVED are reached via goods receiving (CPMAS-31), not
# listed as targets here since nothing in this ticket sets them.
ALLOWED_TRANSITIONS = {
    PurchaseOrder.Status.DRAFT: {PurchaseOrder.Status.SUBMITTED, PurchaseOrder.Status.CANCELLED},
    PurchaseOrder.Status.SUBMITTED: {PurchaseOrder.Status.APPROVED, PurchaseOrder.Status.CANCELLED},
    PurchaseOrder.Status.APPROVED: {PurchaseOrder.Status.CANCELLED},
    PurchaseOrder.Status.PARTIALLY_RECEIVED: set(),
    PurchaseOrder.Status.RECEIVED: set(),
    PurchaseOrder.Status.CANCELLED: set(),
}


def transition_status(purchase_order: PurchaseOrder, new_status: str) -> PurchaseOrder:
    """
    Move a PurchaseOrder to new_status if that's a valid transition from
    its current status; raises ValidationError otherwise.
    """
    current = PurchaseOrder.Status(purchase_order.status)
    target = PurchaseOrder.Status(new_status)

    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValidationError(
            f"Cannot move a purchase order from {current.label} to {target.label}."
        )

    purchase_order.status = target
    purchase_order.save(update_fields=['status', 'updated_at'])
    return purchase_order


# Statuses a PO may be received against: APPROVED (first receipt) or
# PARTIALLY_RECEIVED (a later, additional receipt). Not DRAFT/SUBMITTED
# (never approved), not RECEIVED (already complete), not CANCELLED.
RECEIVABLE_STATUSES = {PurchaseOrder.Status.APPROVED, PurchaseOrder.Status.PARTIALLY_RECEIVED}


def quantity_received_for(po_item: PurchaseOrderItem) -> Decimal:
    """Total quantity received so far against one PO item, across all receipts."""
    total = po_item.goods_receipt_items.aggregate(total=Sum('quantity_received'))['total']
    return total or Decimal('0.000')


def quantity_remaining_for(po_item: PurchaseOrderItem) -> Decimal:
    """BRD 5.15 'Remaining quantity': ordered minus received so far."""
    return po_item.quantity - quantity_received_for(po_item)


@transaction.atomic
def receive_goods(purchase_order: PurchaseOrder, receipt_fields: dict, items_data: list, movement_user) -> GoodsReceipt:
    """
    Record a goods receipt against a purchase order: creates the
    GoodsReceipt and its GoodsReceiptItem rows, applies a matching IN
    StockMovement per item (BRD 5.15 "Receiving materials automatically
    updates inventory"), and recalculates the PO's status from the
    resulting received-vs-ordered totals across ALL its items (not just
    this receipt) -- all in one transaction, so a partially-applied
    receipt (items recorded but stock not updated, or vice versa) can't
    happen.

    receipt_fields: dict of GoodsReceipt field values (purchase_order,
    receipt_number, received_date, warehouse, notes).
    items_data: list of {'purchase_order_item': PurchaseOrderItem,
    'quantity_received': Decimal, 'notes': str} dicts.
    movement_user: the users.User to attribute the resulting stock
    movements to (see the module docstring on why this isn't derived
    from the PO/receipt itself: neither has a users.User column).
    """
    if purchase_order.status not in RECEIVABLE_STATUSES:
        raise ValidationError(
            f"Cannot receive goods against a purchase order that is {purchase_order.get_status_display()}."
        )
    if not items_data:
        raise ValidationError("A goods receipt must include at least one item.")

    receipt = GoodsReceipt.objects.create(purchase_order=purchase_order, **receipt_fields)

    for item_data in items_data:
        po_item = item_data['purchase_order_item']
        quantity = item_data['quantity_received']

        if po_item.purchase_order_id != purchase_order.id:
            raise ValidationError(
                f"PO item {po_item.id} does not belong to purchase order {purchase_order.po_number}."
            )
        if quantity <= 0:
            raise ValidationError("quantity_received must be positive.")

        remaining = quantity_remaining_for(po_item)
        if quantity > remaining:
            raise ValidationError(
                f"Cannot receive {quantity} of {po_item.material} -- only {remaining} remains on this PO line."
            )

        GoodsReceiptItem.objects.create(
            goods_receipt=receipt, purchase_order_item=po_item,
            quantity_received=quantity, notes=item_data.get('notes'),
        )

        movement = StockMovement(
            material=po_item.material, warehouse=receipt.warehouse, quantity=quantity,
            movement_type=StockMovement.MovementType.IN, user=movement_user,
            reference=receipt.receipt_number,
        )
        movement.save()
        apply_stock_movement(movement)

    _recalculate_po_receipt_status(purchase_order)
    return receipt


def _recalculate_po_receipt_status(purchase_order: PurchaseOrder) -> PurchaseOrder:
    """
    After a receipt is recorded, move the PO to RECEIVED if every item is
    now fully received, or PARTIALLY_RECEIVED if at least one item has
    received > 0 but not all are complete. Bypasses transition_status's
    user-facing ALLOWED_TRANSITIONS map on purpose -- this is a derived
    state change driven by actual receiving, not a user action to
    validate against a manual workflow.
    """
    items = list(purchase_order.items.all())
    received_totals = [quantity_received_for(item) for item in items]

    if all(received >= item.quantity for received, item in zip(received_totals, items)):
        new_status = PurchaseOrder.Status.RECEIVED
    elif any(received > 0 for received in received_totals):
        new_status = PurchaseOrder.Status.PARTIALLY_RECEIVED
    else:
        new_status = purchase_order.status

    if new_status != purchase_order.status:
        purchase_order.status = new_status
        purchase_order.save(update_fields=['status', 'updated_at'])
    return purchase_order
