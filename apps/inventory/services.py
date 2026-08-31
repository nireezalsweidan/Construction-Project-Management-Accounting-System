"""
Business logic for the ``inventory`` app that must not live in a
serializer or viewset -- specifically, the single code path allowed to
change a ``Stock`` row's quantity (BR 12.6: "Inventory quantity updated
exclusively through stock movements").

Keeping this in one function makes that rule structurally enforced rather
than just documented: nothing else in the codebase should ever call
``Stock.objects.filter(...).update(quantity=...)`` or set
``stock.quantity = ...; stock.save()`` directly.
"""
from django.db import transaction

from .models import Stock


@transaction.atomic
def apply_stock_movement(movement):
    """
    Apply an already-created StockMovement to its Stock balance.

    Uses select_for_update so two concurrent movements against the same
    (warehouse, material) -- e.g. two goods receipts landing at once --
    serialize on this row instead of racing and losing one update. Runs
    inside the same atomic block the caller's StockMovement.save() should
    already be wrapped in (see InventorySerializer/viewset), so a failure
    here rolls back the ledger entry too rather than leaving the two out
    of sync.
    """
    stock, _ = Stock.objects.select_for_update().get_or_create(
        warehouse=movement.warehouse,
        material=movement.material,
        defaults={'quantity': 0},
    )
    stock.quantity = stock.quantity + movement.quantity
    stock.save(update_fields=['quantity', 'updated_at'])
    return stock
