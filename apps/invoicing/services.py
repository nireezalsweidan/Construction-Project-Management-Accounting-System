"""
Business logic for the ``invoicing`` app that must not live in a
serializer or viewset.

Same reasoning as purchasing.services (CPMAS-30): centralizing these
rules in one place makes them structurally enforced rather than just
documented.

1. Monetary totals are always computed here, not accepted as direct API
   input for the invoice header.
2. SupplierInvoice.status only ever changes through transition_status,
   validated against ALLOWED_TRANSITIONS.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import SupplierInvoice, SupplierInvoiceItem

TWO_PLACES = Decimal('0.01')


def compute_item_amounts(item: SupplierInvoiceItem) -> SupplierInvoiceItem:
    """
    Set tax_amount and total_amount on a (not-yet-saved) SupplierInvoiceItem.

    Two cases, per the schema allowing quantity/unit_price to be null
    (unlike PurchaseOrderItem, where both are required):

    - Both quantity and unit_price are given: derive exactly like a PO
      item (quantity * unit_price, plus tax_rate.rate% if set) --
      whatever tax_amount/total_amount the caller sent are overwritten.
    - Either is missing (a flat-charge line, e.g. a delivery fee): there
      is nothing to multiply, so the caller-supplied total_amount is
      trusted as-is; tax_amount defaults to 0 unless the caller already
      set one (a flat charge can still carry its own tax figure without
      a quantity/price breakdown).
    """
    if item.quantity is not None and item.unit_price is not None:
        line_subtotal = (item.quantity * item.unit_price).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        if item.tax_rate_id and item.tax_rate:
            tax_amount = (line_subtotal * item.tax_rate.rate / Decimal('100')).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        else:
            tax_amount = Decimal('0.00')

        item.tax_amount = tax_amount
        item.total_amount = line_subtotal + tax_amount
    else:
        # Flat-charge line: nothing to derive from, keep whatever the
        # caller provided (defaulting to 0 if they provided nothing).
        item.tax_amount = item.tax_amount or Decimal('0.00')
        item.total_amount = item.total_amount or Decimal('0.00')

    return item


@transaction.atomic
def recalculate_invoice_totals(invoice: SupplierInvoice) -> SupplierInvoice:
    """
    Recompute a SupplierInvoice's subtotal/tax_amount/total_amount from
    its current line items.

    subtotal is derived as (total_amount - tax_amount) per line rather
    than re-deriving quantity*unit_price, so it works uniformly whether
    a given line's amounts came from the quantity/price path or were
    supplied directly as a flat charge (see compute_item_amounts).
    """
    items = invoice.items.all()

    subtotal_sum = sum((i.total_amount - i.tax_amount for i in items), Decimal('0.00'))
    tax_sum = sum((i.tax_amount for i in items), Decimal('0.00'))
    total_sum = sum((i.total_amount for i in items), Decimal('0.00'))

    invoice.subtotal = subtotal_sum
    invoice.tax_amount = tax_sum
    invoice.total_amount = total_sum
    invoice.save(update_fields=['subtotal', 'tax_amount', 'total_amount', 'updated_at'])
    return invoice


# PARTIALLY_PAID/PAID/OVERDUE are not reachable here -- they depend on
# payment allocations, which don't exist yet (see module docstring).
ALLOWED_TRANSITIONS = {
    SupplierInvoice.Status.DRAFT: {SupplierInvoice.Status.SENT, SupplierInvoice.Status.CANCELLED},
    SupplierInvoice.Status.SENT: {SupplierInvoice.Status.CANCELLED},
    SupplierInvoice.Status.PARTIALLY_PAID: set(),
    SupplierInvoice.Status.PAID: set(),
    SupplierInvoice.Status.OVERDUE: set(),
    SupplierInvoice.Status.CANCELLED: set(),
}


def transition_status(invoice: SupplierInvoice, new_status: str) -> SupplierInvoice:
    """Move a SupplierInvoice to new_status if valid; raises ValidationError otherwise."""
    current = SupplierInvoice.Status(invoice.status)
    target = SupplierInvoice.Status(new_status)

    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValidationError(
            f"Cannot move a supplier invoice from {current.label} to {target.label}."
        )

    invoice.status = target
    invoice.save(update_fields=['status', 'updated_at'])
    return invoice
