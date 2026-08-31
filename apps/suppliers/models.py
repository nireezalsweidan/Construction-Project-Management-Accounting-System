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
