"""
Business logic for the ``purchasing`` app that must not live in a
serializer or viewset.

Two concerns are centralized here, each for the same reason
``inventory.services.apply_stock_movement`` exists: making a business
rule a single, explicitly-called function instead of scattered
serializer/view logic means it can't be silently bypassed by a future
code path.

1. Monetary totals (PurchaseOrderItem.tax_amount/total_amount,
   PurchaseOrder.subtotal/tax_amount/total_amount) are always computed
   here from quantity/unit_price/tax_rate -- never accepted as direct
   API input.
2. PurchaseOrder.status only ever changes through ``transition_status``,
   which validates the transition against ``ALLOWED_TRANSITIONS`` --
   never a raw field assignment -- so a client can't jump e.g. straight
   from DRAFT to RECEIVED without ever being APPROVED.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import PurchaseOrder, PurchaseOrderItem

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
