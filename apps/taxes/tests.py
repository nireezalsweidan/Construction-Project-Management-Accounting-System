"""
Tests for the ``taxes`` app (CPMAS-28: minimal TaxRate model).

Covers the schema-mandated shape of TaxRate: required fields, decimal
precision on ``rate``, and default ordering.
"""
from decimal import Decimal

from django.test import TestCase

from .models import TaxRate


class TaxRateModelTests(TestCase):
    def test_create_with_required_fields(self):
        tax = TaxRate.objects.create(
            name="VAT 15%", rate=Decimal("15.0000"), tax_type="VAT",
            effective_date="2026-01-01",
        )
        self.assertTrue(tax.is_active)  # default=True per the schema
        self.assertEqual(str(tax), "VAT 15% (15.0000%)")

    def test_rate_precision_is_preserved(self):
        # DECIMAL(8,4) in the schema -- verify four decimal places survive
        # a round trip through the database, not just in memory.
        tax = TaxRate.objects.create(
            name="Fractional", rate=Decimal("7.2534"), tax_type="Sales Tax",
            effective_date="2026-01-01",
        )
        tax.refresh_from_db()
        self.assertEqual(tax.rate, Decimal("7.2534"))

    def test_default_ordering_is_name_then_effective_date_desc(self):
        old = TaxRate.objects.create(name="A", rate=Decimal("1"), tax_type="VAT", effective_date="2020-01-01")
        new = TaxRate.objects.create(name="A", rate=Decimal("2"), tax_type="VAT", effective_date="2026-01-01")
        other = TaxRate.objects.create(name="B", rate=Decimal("3"), tax_type="VAT", effective_date="2021-01-01")
        self.assertEqual(list(TaxRate.objects.all()), [new, old, other])
