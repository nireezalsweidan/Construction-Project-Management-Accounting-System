"""
Tests for the ``invoicing`` app -- Supplier Invoices slice (CPMAS-32).

Organized into:
- Service tests: compute_item_amounts (both the quantity*price derivation
  path and the flat-charge path), recalculate_invoice_totals, and
  transition_status.
- API tests: the same behaviors through the real DRF endpoints --
  status-change actions, DRAFT-lock enforcement, and the
  both-or-neither quantity/unit_price validation rule.
"""
from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from inventory.models import Material, MaterialCategory
from suppliers.models import Supplier
from taxes.models import TaxRate

from .models import SupplierInvoice, SupplierInvoiceItem
from .services import compute_item_amounts, recalculate_invoice_totals, transition_status


class InvoicingTestBase(TestCase):
    """Shared fixtures: a supplier, a material (for line items), a tax rate."""

    def setUp(self):
        self.supplier = Supplier.objects.create(name="ACME Building Supplies")
        category = MaterialCategory.objects.create(name="Cement")
        self.material = Material.objects.create(category=category, name="Portland Cement", sku="CEM-SI-1", unit="bag")
        self.tax = TaxRate.objects.create(name="VAT 15%", rate=Decimal("15.0000"), tax_type="VAT", effective_date="2026-01-01")

    def make_invoice(self, **kwargs):
        defaults = dict(supplier=self.supplier, invoice_number="INV-0001", invoice_date="2026-08-31")
        defaults.update(kwargs)
        return SupplierInvoice.objects.create(**defaults)


class ComputeItemAmountsTests(InvoicingTestBase):
    def test_quantity_and_price_path_derives_amounts(self):
        invoice = self.make_invoice()
        item = SupplierInvoiceItem(supplier_invoice=invoice, description="Cement", quantity=Decimal("10"), unit_price=Decimal("5.00"), tax_rate=self.tax)
        compute_item_amounts(item)
        self.assertEqual(item.tax_amount, Decimal("7.50"))
        self.assertEqual(item.total_amount, Decimal("57.50"))

    def test_flat_charge_line_keeps_caller_supplied_total(self):
        invoice = self.make_invoice()
        item = SupplierInvoiceItem(supplier_invoice=invoice, description="Delivery fee", total_amount=Decimal("25.00"), tax_amount=Decimal("2.50"))
        compute_item_amounts(item)
        # No quantity/unit_price to derive from -- caller-supplied values pass through untouched.
        self.assertEqual(item.tax_amount, Decimal("2.50"))
        self.assertEqual(item.total_amount, Decimal("25.00"))

    def test_quantity_and_price_path_overrides_a_supplied_total(self):
        # tax_amount/total_amount are writable on the serializer (needed
        # for the flat-charge path) -- prove the derivation path still
        # wins and a caller can't smuggle a bogus total past it by
        # supplying quantity/unit_price AND a mismatched total_amount.
        invoice = self.make_invoice()
        item = SupplierInvoiceItem(
            supplier_invoice=invoice, description="Cement", quantity=Decimal("10"),
            unit_price=Decimal("5.00"), tax_rate=self.tax, total_amount=Decimal("999999.00"),
        )
        compute_item_amounts(item)
        self.assertEqual(item.total_amount, Decimal("57.50"))

    def test_flat_charge_line_defaults_to_zero_if_not_supplied(self):
        invoice = self.make_invoice()
        item = SupplierInvoiceItem(supplier_invoice=invoice, description="Placeholder line")
        compute_item_amounts(item)
        self.assertEqual(item.tax_amount, Decimal("0.00"))
        self.assertEqual(item.total_amount, Decimal("0.00"))


class RecalculateInvoiceTotalsTests(InvoicingTestBase):
    def test_totals_sum_across_mixed_line_types(self):
        invoice = self.make_invoice()

        priced_item = SupplierInvoiceItem(supplier_invoice=invoice, description="Cement", quantity=Decimal("10"), unit_price=Decimal("5.00"), tax_rate=self.tax)
        compute_item_amounts(priced_item)
        priced_item.save()

        flat_item = SupplierInvoiceItem(supplier_invoice=invoice, description="Delivery fee", total_amount=Decimal("20.00"), tax_amount=Decimal("0.00"))
        compute_item_amounts(flat_item)
        flat_item.save()

        recalculate_invoice_totals(invoice)
        invoice.refresh_from_db()
        # priced: subtotal 50.00 + tax 7.50 = 57.50; flat: 20.00 + 0 = 20.00
        self.assertEqual(invoice.subtotal, Decimal("70.00"))
        self.assertEqual(invoice.tax_amount, Decimal("7.50"))
        self.assertEqual(invoice.total_amount, Decimal("77.50"))


class TransitionStatusTests(InvoicingTestBase):
    def test_draft_to_sent(self):
        invoice = self.make_invoice()
        transition_status(invoice, SupplierInvoice.Status.SENT)
        self.assertEqual(invoice.status, SupplierInvoice.Status.SENT)

    def test_cannot_skip_to_paid(self):
        invoice = self.make_invoice()
        with self.assertRaises(ValidationError):
            transition_status(invoice, SupplierInvoice.Status.PAID)

    def test_can_cancel_from_sent(self):
        invoice = self.make_invoice()
        transition_status(invoice, SupplierInvoice.Status.SENT)
        transition_status(invoice, SupplierInvoice.Status.CANCELLED)
        self.assertEqual(invoice.status, SupplierInvoice.Status.CANCELLED)

    def test_cannot_leave_cancelled(self):
        invoice = self.make_invoice()
        transition_status(invoice, SupplierInvoice.Status.CANCELLED)
        with self.assertRaises(ValidationError):
            transition_status(invoice, SupplierInvoice.Status.DRAFT)


class SupplierInvoiceAPITests(InvoicingTestBase):
    def setUp(self):
        super().setUp()
        django_user = DjangoUser.objects.create_user(username="apitester", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(user=django_user)

    def test_create_invoice_and_priced_item_computes_totals(self):
        create_response = self.client.post("/api/invoicing/supplier-invoices/", {
            "supplier": str(self.supplier.id), "invoice_number": "INV-API-1", "invoice_date": "2026-08-31",
        }, format="json")
        self.assertEqual(create_response.status_code, 201)
        invoice_id = create_response.json()["id"]

        item_response = self.client.post("/api/invoicing/supplier-invoice-items/", {
            "supplier_invoice": invoice_id, "description": "Cement", "material": str(self.material.id),
            "quantity": "4", "unit_price": "25.00",
        }, format="json")
        self.assertEqual(item_response.status_code, 201)

        invoice_response = self.client.get(f"/api/invoicing/supplier-invoices/{invoice_id}/")
        self.assertEqual(invoice_response.json()["total_amount"], "100.00")

    def test_flat_charge_item_via_api(self):
        invoice = self.make_invoice(invoice_number="INV-API-2")
        response = self.client.post("/api/invoicing/supplier-invoice-items/", {
            "supplier_invoice": str(invoice.id), "description": "Delivery fee", "total_amount": "15.00",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["total_amount"], "15.00")

    def test_quantity_without_unit_price_is_rejected(self):
        invoice = self.make_invoice(invoice_number="INV-API-3")
        response = self.client.post("/api/invoicing/supplier-invoice-items/", {
            "supplier_invoice": str(invoice.id), "description": "Bad line", "quantity": "5",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_status_cannot_be_set_directly_via_patch(self):
        invoice = self.make_invoice(invoice_number="INV-API-4")
        response = self.client.patch(f"/api/invoicing/supplier-invoices/{invoice.id}/", {"status": "PAID"}, format="json")
        self.assertEqual(response.json()["status"], "DRAFT")

    def test_mark_sent_and_cancel_workflow(self):
        invoice = self.make_invoice(invoice_number="INV-API-5")
        sent = self.client.post(f"/api/invoicing/supplier-invoices/{invoice.id}/mark_sent/")
        self.assertEqual(sent.json()["status"], "SENT")
        cancelled = self.client.post(f"/api/invoicing/supplier-invoices/{invoice.id}/cancel/")
        self.assertEqual(cancelled.json()["status"], "CANCELLED")

    def test_items_locked_once_invoice_leaves_draft(self):
        invoice = self.make_invoice(invoice_number="INV-API-6")
        self.client.post(f"/api/invoicing/supplier-invoices/{invoice.id}/mark_sent/")
        response = self.client.post("/api/invoicing/supplier-invoice-items/", {
            "supplier_invoice": str(invoice.id), "description": "Too late",
        }, format="json")
        self.assertEqual(response.status_code, 403)

    def test_anonymous_request_is_rejected(self):
        anon = APIClient()
        response = anon.get("/api/invoicing/supplier-invoices/")
        # 401 (not 403): with the auth ticket in place, unauthenticated
        # requests are challenged to authenticate before access is denied.
        self.assertEqual(response.status_code, 401)
