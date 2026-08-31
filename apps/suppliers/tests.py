"""
Tests for the ``suppliers`` app (CPMAS-28: minimal Supplier model).

Covers required vs. optional fields and the auto-managed audit
timestamps (added after reconciling against the live database's actual
schema -- see CPMAS-28's follow-up commit).
"""
import time

from django.test import TestCase

from .models import Supplier


class SupplierModelTests(TestCase):
    def test_create_with_only_required_fields(self):
        supplier = Supplier.objects.create(name="ACME Building Supplies")
        self.assertIsNone(supplier.company_name)
        self.assertTrue(supplier.is_active)  # default=True
        self.assertEqual(str(supplier), "ACME Building Supplies")

    def test_timestamps_are_set_automatically(self):
        supplier = Supplier.objects.create(name="ACME")
        self.assertIsNotNone(supplier.created_at)
        self.assertIsNotNone(supplier.updated_at)

    def test_updated_at_changes_on_save(self):
        supplier = Supplier.objects.create(name="ACME")
        original_updated_at = supplier.updated_at
        time.sleep(0.01)  # guarantee a distinct auto_now timestamp
        supplier.notes = "Preferred vendor"
        supplier.save()
        self.assertGreater(supplier.updated_at, original_updated_at)
