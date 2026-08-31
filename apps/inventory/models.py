"""
Models for the ``inventory`` app -- Material Management slice (CPMAS-28).

Implements the material catalog: ``MaterialCategory`` and ``Material``,
matching the ``material_categories`` and ``materials`` tables in the
approved database schema (BRD 5.12 Material Management).

Warehouse/stock/stock-movement models (BRD 5.13 Inventory Management,
CPMAS-29) are added to this same app in the next Sprint 2 task -- the
schema groups Materials, Warehouses, Stock and Stock Movements together
under a single ``inventory/`` Django app, since stock rows and movements
both reference ``Material`` directly.
"""
import uuid

from django.db import models


class MaterialCategory(models.Model):
    """
    Grouping for materials (e.g. "Cement", "Steel", "Electrical").

    Matches the ``material_categories`` table in the approved schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
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
    # meters of concrete).
    minimum_stock_level = models.DecimalField(max_digits=18, decimal_places=3)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'materials'
        ordering = ['name']
        verbose_name = 'Material'
        verbose_name_plural = 'Materials'

    def __str__(self):
        return f"{self.name} ({self.sku})"
