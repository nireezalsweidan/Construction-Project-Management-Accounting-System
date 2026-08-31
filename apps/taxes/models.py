"""
Models for the ``taxes`` app.

Provides the ``TaxRate`` reference table used across the system wherever a
tax needs to be applied and calculated: materials (default tax), purchase
order / supplier invoice / client invoice line items, and expenses.

This model is built now, ahead of its own "Tax Management" ticket, purely
as a foreign-key target for ``inventory.Material.tax_rate`` (CPMAS-28). It
already implements the full ``tax_rates`` table from the approved database
schema, so the owning ticket for Tax Management should not need to modify
this model's shape -- only add the CRUD API/business logic around it.
"""
import uuid

from django.db import models


class TaxRate(models.Model):
    """
    A configurable tax rate (e.g. VAT, sales tax) that can be applied to
    materials, invoice lines, purchase order lines, and expenses.

    Fields and constraints follow the ``tax_rates`` table in the approved
    database schema exactly (BRD 5.21 Tax Management).
    """

    # UUID primary key, matching the schema's convention of UUID identifiers
    # for every table (rather than Django's default integer/BigAutoField).
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=100)

    # DECIMAL(8,4) in the schema: supports rates like 15.0000% with enough
    # precision to avoid rounding drift across many line items.
    rate = models.DecimalField(max_digits=8, decimal_places=4)

    # e.g. "VAT", "Sales Tax" -- kept as free text per the schema rather than
    # a hardcoded choices list, since taxation terminology varies by country.
    tax_type = models.CharField(max_length=50)

    effective_date = models.DateField()

    # Whether this rate is currently selectable/applicable. Historical rates
    # are kept (never deleted) so past transactions still resolve their tax
    # rate correctly; they're just excluded from new selections when False.
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'tax_rates'
        ordering = ['name', '-effective_date']
        verbose_name = 'Tax Rate'
        verbose_name_plural = 'Tax Rates'

    def __str__(self):
        return f"{self.name} ({self.rate}%)"
