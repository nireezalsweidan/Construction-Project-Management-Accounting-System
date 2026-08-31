"""
Models for the ``inventory`` app.

Implements the full BRD 5.12/5.13 Material & Inventory Management slice:
- ``MaterialCategory`` / ``Material`` -- the material catalog (CPMAS-28),
  matching the ``material_categories`` / ``materials`` tables.
- ``Warehouse`` / ``Stock`` / ``StockMovement`` -- warehouses, current
  on-hand quantities, and the movement ledger (CPMAS-29), matching the
  ``warehouses`` / ``stocks`` / ``stock_movements`` tables.

Business rule 12.6 ("Inventory quantity updated exclusively through stock
movements") is enforced by treating ``Stock.quantity`` as a value only
ever written by ``inventory.services.apply_stock_movement`` -- never
accepted as writable input on the Stock API -- and by exposing
``StockMovement`` as an append-only ledger (create/read only, no
update/delete) rather than a freely editable table.

``StockMovement.project`` is intentionally NOT modeled yet: the schema
defines it as an optional FK into ``projects.Project``, but that app (and
its own manager FK into ``employees.Employee``) belongs to other,
currently unbuilt tickets. Adding it later is a straightforward additive
migration once those land.
"""
import uuid

from django.db import models
from django.utils import timezone


class MaterialCategory(models.Model):
    """
    Grouping for materials (e.g. "Cement", "Steel", "Electrical").

    Matches the ``material_categories`` table in the approved schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # unique=True matches a UNIQUE constraint already present on the live
    # database table -- two categories with the same name would make the
    # material catalog's grouping ambiguous.
    name = models.CharField(max_length=150, unique=True)

    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'material_categories'
        ordering = ['name']
        verbose_name = 'Material Category'
        verbose_name_plural = 'Material Categories'

    def __str__(self):
        return self.name


class Material(models.Model):
    """
    A purchasable/stockable material (e.g. Cement, Steel, Bricks, Pipes).

    Matches the ``materials`` table in the approved schema. Stock levels
    themselves are NOT tracked on this model -- per business rule 12.6
    ("Inventory quantity updated exclusively through stock movements"),
    on-hand quantity lives on the ``Stock`` model (CPMAS-29) and is derived
    from ``StockMovement`` rows, never edited directly here.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT: a category in use by materials should not be silently
    # deletable, since that would orphan the material catalog. Category
    # deletion should be an explicit, deliberate re-categorization step.
    category = models.ForeignKey(
        MaterialCategory,
        on_delete=models.PROTECT,
        related_name='materials',
    )

    name = models.CharField(max_length=255)

    # Stock Keeping Unit. The approved schema marks this NOT NULL but does
    # not explicitly state UNIQUE; unique=True is added here as a data
    # -integrity safeguard -- two materials sharing a SKU would make goods
    # receiving, stock movements, and purchase order lines ambiguous.
    sku = models.CharField(max_length=100, unique=True)

    # Unit of measure (e.g. "bag", "kg", "m", "unit"). Free text per the
    # schema rather than a fixed choices list, since units vary widely
    # across material types.
    unit = models.CharField(max_length=50)

    description = models.TextField(blank=True, null=True)

    standard_cost = models.DecimalField(
        max_digits=18, decimal_places=2, blank=True, null=True,
    )

    # SET_NULL: if a tax rate is retired/removed, existing materials should
    # keep working (fall back to no default tax) rather than being blocked
    # or cascading a delete into the material catalog.
    tax_rate = models.ForeignKey(
        'taxes.TaxRate',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='materials',
    )

    # SET_NULL for the same reason: losing a default supplier shouldn't
    # delete the material -- purchasing can simply pick a supplier manually
    # on the next purchase order.
    default_supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='default_for_materials',
    )

    # Reorder/low-stock alert threshold (BRD 5.13: "Low-stock alerts").
    # DECIMAL(18,3) in the schema to support fractional units (e.g. cubic
    # meters of concrete). default=0 matches the live database column's
    # default so creating a Material without specifying this explicitly
    # behaves identically at the ORM and DB layers.
    minimum_stock_level = models.DecimalField(max_digits=18, decimal_places=3, default=0)

    is_active = models.BooleanField(default=True)

    # Audit timestamps -- see the same note on suppliers.Supplier.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'materials'
        ordering = ['name']
        verbose_name = 'Material'
        verbose_name_plural = 'Materials'

    def __str__(self):
        return f"{self.name} ({self.sku})"


class Warehouse(models.Model):
    """
    A physical storage location materials are held at.

    Matches the ``warehouses`` table in the approved schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    location = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'warehouses'
        ordering = ['name']
        verbose_name = 'Warehouse'
        verbose_name_plural = 'Warehouses'

    def __str__(self):
        return self.name


class Stock(models.Model):
    """
    Current on-hand quantity of one material at one warehouse.

    Matches the ``stocks`` table. ``quantity`` must never be written
    directly through the API -- per BR 12.6, it is only ever mutated by
    ``inventory.services.apply_stock_movement`` in response to a new
    ``StockMovement``. The serializer/viewset for this model expose it as
    read-only to enforce that at the API layer too.

    unique_together enforces exactly one balance row per (warehouse,
    material) pair -- correcting a bug found in the live database, which
    originally had separate single-column UNIQUE constraints on
    warehouse_id and material_id individually (limiting a material to a
    single warehouse system-wide). Reconciled via migration 0002, which
    drops those two constraints and adds this composite one.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT: a warehouse/material with recorded stock shouldn't be
    # deletable out from under that balance -- deactivate (is_active=False)
    # instead of deleting.
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='stocks')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='stocks')

    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stocks'
        ordering = ['warehouse__name', 'material__name']
        unique_together = [('warehouse', 'material')]
        verbose_name = 'Stock'
        verbose_name_plural = 'Stocks'

    def __str__(self):
        return f"{self.material} @ {self.warehouse}: {self.quantity}"


class StockMovement(models.Model):
    """
    An immutable ledger entry recording a change in stock quantity.

    Matches the ``stock_movements`` table (minus ``project_id`` -- see the
    module docstring). ``movement_type`` values match the live Postgres
    enum ``movement_type_enum`` exactly (IN/OUT/RETURN/TRANSFER/ADJUSTMENT)
    rather than the more granular categories BRD 5.13 lists in prose
    (Purchase, Project Usage, ...) -- the ``reference``/``notes`` fields
    carry that business context instead (e.g. a PO number for an IN
    movement caused by a goods receipt).

    ``quantity`` is a signed magnitude: positive for movements that
    increase stock (IN, RETURN, and the destination leg of a TRANSFER),
    negative for movements that decrease it (OUT, ADJUSTMENT down, and the
    source leg of a TRANSFER). This is the one place this app's design
    deviates from a literal reading of "quantity DECIMAL(18,3) NOT NULL"
    in the schema -- it doesn't forbid negative values, and a signed
    quantity is what lets ``apply_stock_movement`` update Stock with a
    single addition regardless of movement type.
    """

    class MovementType(models.TextChoices):
        IN = 'IN', 'In'
        OUT = 'OUT', 'Out'
        RETURN = 'RETURN', 'Return'
        TRANSFER = 'TRANSFER', 'Transfer'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT throughout: a movement is a historical ledger entry -- the
    # material/warehouse/user it references should never be deletable out
    # from under it, since that would corrupt the audit trail.
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='stock_movements')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='stock_movements')

    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    movement_date = models.DateTimeField(default=timezone.now)

    # References apps.users.User (the existing, unmanaged reflection of the
    # live `users` table) rather than Django's default auth user model --
    # the live FK constraint on stock_movements.user_id targets `users`,
    # not `auth_user`, so this is the only model that can satisfy it.
    user = models.ForeignKey('users.User', on_delete=models.PROTECT, related_name='stock_movements')

    reference = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'stock_movements'
        ordering = ['-movement_date']
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'

    def __str__(self):
        return f"{self.movement_type} {self.quantity} of {self.material} @ {self.warehouse}"
