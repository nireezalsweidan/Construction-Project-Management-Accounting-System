"""
Tests for the ``invoicing`` app -- Supplier Invoices (CPMAS-32) and
Client Invoices (CPMAS-35) slices.

Organized into:
- Service tests: compute_item_amounts (both the quantity*price derivation
  path and the flat-charge path), recalculate_invoice_totals, and
  transition_status -- for both SupplierInvoice and (the CPMAS-35
  additions) ClientInvoice.
- API tests: the same behaviors through the real DRF endpoints --
  status-change actions, DRAFT-lock enforcement, and validation rules.
"""
from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from clients.models import Client
from clients.testing import WithClientsTableMixin
from inventory.models import Material, MaterialCategory
from projects.testing import WithProjectsTableMixin
from suppliers.models import Supplier
from taxes.models import TaxRate

from .models import ClientInvoice, ClientInvoiceItem, SupplierInvoice, SupplierInvoiceItem
from .services import (
    compute_client_invoice_item_amounts,
    compute_item_amounts,
    recalculate_client_invoice_totals,
    recalculate_invoice_totals,
    transition_client_invoice_status,
    transition_status,
)


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


class ClientInvoicingTestBase(WithClientsTableMixin, WithProjectsTableMixin, TestCase):
    """Shared fixtures for the ClientInvoice (CPMAS-35) test classes: a client, a tax rate."""

    def setUp(self):
        self.client_obj = Client.objects.create(name="Jane Homeowner")
        self.tax = TaxRate.objects.create(name="VAT 15%", rate=Decimal("15.0000"), tax_type="VAT", effective_date="2026-01-01")

    def make_client_invoice(self, **kwargs):
        defaults = dict(client=self.client_obj, invoice_number="CINV-0001", invoice_date="2026-08-31")
        defaults.update(kwargs)
        return ClientInvoice.objects.create(**defaults)


class ComputeClientInvoiceItemAmountsTests(ClientInvoicingTestBase):
    def test_derives_tax_and_total_from_quantity_and_price(self):
        invoice = self.make_client_invoice()
        item = ClientInvoiceItem(client_invoice=invoice, description="Tile installation", quantity=Decimal("10"), unit_price=Decimal("20.00"), tax_rate=self.tax)
        compute_client_invoice_item_amounts(item)
        # gross 200.00, tax 15% of 200.00 = 30.00
        self.assertEqual(item.tax_amount, Decimal("30.00"))
        self.assertEqual(item.total_amount, Decimal("230.00"))

    def test_discount_is_subtracted_before_tax(self):
        invoice = self.make_client_invoice()
        item = ClientInvoiceItem(client_invoice=invoice, description="Tile installation", quantity=Decimal("10"), unit_price=Decimal("20.00"), discount_amount=Decimal("50.00"), tax_rate=self.tax)
        compute_client_invoice_item_amounts(item)
        # gross 200.00 - discount 50.00 = 150.00; tax 15% of 150.00 = 22.50
        self.assertEqual(item.tax_amount, Decimal("22.50"))
        self.assertEqual(item.total_amount, Decimal("172.50"))

    def test_no_tax_rate_means_zero_tax(self):
        invoice = self.make_client_invoice()
        item = ClientInvoiceItem(client_invoice=invoice, description="Labor", quantity=Decimal("5"), unit_price=Decimal("10.00"))
        compute_client_invoice_item_amounts(item)
        self.assertEqual(item.tax_amount, Decimal("0.00"))
        self.assertEqual(item.total_amount, Decimal("50.00"))


class RecalculateClientInvoiceTotalsTests(ClientInvoicingTestBase):
    def test_totals_sum_across_lines(self):
        invoice = self.make_client_invoice()

        item_a = ClientInvoiceItem(client_invoice=invoice, description="Tiles", quantity=Decimal("10"), unit_price=Decimal("20.00"), tax_rate=self.tax)
        compute_client_invoice_item_amounts(item_a)
        item_a.save()

        item_b = ClientInvoiceItem(client_invoice=invoice, description="Labor", quantity=Decimal("5"), unit_price=Decimal("10.00"), discount_amount=Decimal("5.00"))
        compute_client_invoice_item_amounts(item_b)
        item_b.save()

        recalculate_client_invoice_totals(invoice)
        invoice.refresh_from_db()
        # item_a: gross 200.00, tax 30.00, total 230.00
        # item_b: gross 50.00, discount 5.00, no tax, total 45.00
        self.assertEqual(invoice.subtotal, Decimal("250.00"))
        self.assertEqual(invoice.discount_amount, Decimal("5.00"))
        self.assertEqual(invoice.tax_amount, Decimal("30.00"))
        self.assertEqual(invoice.total_amount, Decimal("275.00"))


class TransitionClientInvoiceStatusTests(ClientInvoicingTestBase):
    def test_draft_to_sent(self):
        invoice = self.make_client_invoice()
        transition_client_invoice_status(invoice, ClientInvoice.Status.SENT)
        self.assertEqual(invoice.status, ClientInvoice.Status.SENT)

    def test_cannot_skip_to_paid(self):
        invoice = self.make_client_invoice()
        with self.assertRaises(ValidationError):
            transition_client_invoice_status(invoice, ClientInvoice.Status.PAID)

    def test_cannot_leave_cancelled(self):
        invoice = self.make_client_invoice()
        transition_client_invoice_status(invoice, ClientInvoice.Status.CANCELLED)
        with self.assertRaises(ValidationError):
            transition_client_invoice_status(invoice, ClientInvoice.Status.DRAFT)


class ClientInvoiceAPITests(ClientInvoicingTestBase):
    def setUp(self):
        super().setUp()
        django_user = DjangoUser.objects.create_user(username="apitester2", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(user=django_user)

    def test_create_invoice_and_item_computes_totals(self):
        create_response = self.client.post("/api/invoicing/client-invoices/", {
            "client": str(self.client_obj.id), "invoice_number": "CINV-API-1", "invoice_date": "2026-08-31",
        }, format="json")
        self.assertEqual(create_response.status_code, 201)
        invoice_id = create_response.json()["id"]

        item_response = self.client.post("/api/invoicing/client-invoice-items/", {
            "client_invoice": invoice_id, "description": "Tiles", "quantity": "4", "unit_price": "25.00",
        }, format="json")
        self.assertEqual(item_response.status_code, 201)

        invoice_response = self.client.get(f"/api/invoicing/client-invoices/{invoice_id}/")
        self.assertEqual(invoice_response.json()["total_amount"], "100.00")
        self.assertEqual(invoice_response.json()["outstanding_balance"], "0.00")  # still DRAFT

    def test_status_cannot_be_set_directly_via_patch(self):
        invoice = self.make_client_invoice(invoice_number="CINV-API-2")
        response = self.client.patch(f"/api/invoicing/client-invoices/{invoice.id}/", {"status": "PAID"}, format="json")
        self.assertEqual(response.json()["status"], "DRAFT")

    def test_mark_sent_and_cancel_workflow(self):
        invoice = self.make_client_invoice(invoice_number="CINV-API-3")
        sent = self.client.post(f"/api/invoicing/client-invoices/{invoice.id}/mark_sent/")
        self.assertEqual(sent.json()["status"], "SENT")
        cancelled = self.client.post(f"/api/invoicing/client-invoices/{invoice.id}/cancel/")
        self.assertEqual(cancelled.json()["status"], "CANCELLED")

    def test_items_locked_once_invoice_leaves_draft(self):
        invoice = self.make_client_invoice(invoice_number="CINV-API-4")
        self.client.post(f"/api/invoicing/client-invoices/{invoice.id}/mark_sent/")
        response = self.client.post("/api/invoicing/client-invoice-items/", {
            "client_invoice": str(invoice.id), "description": "Too late", "quantity": "1", "unit_price": "1.00",
        }, format="json")
        self.assertEqual(response.status_code, 403)

    def test_outstanding_balance_equals_total_once_sent(self):
        invoice = self.make_client_invoice(invoice_number="CINV-API-5", total_amount=Decimal("500.00"))
        self.client.post(f"/api/invoicing/client-invoices/{invoice.id}/mark_sent/")
        response = self.client.get(f"/api/invoicing/client-invoices/{invoice.id}/")
        self.assertEqual(response.json()["outstanding_balance"], "500.00")

    def test_anonymous_request_is_rejected(self):
        anon = APIClient()
        response = anon.get("/api/invoicing/client-invoices/")
        self.assertEqual(response.status_code, 401)
