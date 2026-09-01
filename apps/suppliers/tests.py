"""
Tests for the ``suppliers`` app -- Supplier Management.

Two groups:
- model tests (the original CPMAS-28 set covering the Supplier record),
- Supplier Management API tests: CRUD, currency constant, and the
  purchase-orders / invoices / payments / receipts / balance detail actions.

Suppliers are pure data records: nothing here creates authentication,
login, or a role for them -- the API is exercised exactly like the rest of
the system, as a logged-in internal user (Django auth user + DRF
SessionAuthentication / IsAuthenticated).
"""
import time
import uuid
from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from rest_framework.test import APIClient

from clients.models import ClientPayment, PaymentAllocation
from invoicing.models import SupplierInvoice
from purchasing.models import PurchaseOrder
from users.models import User
from users.testing import WithUsersTableMixin

from .models import ReceiptSummary, Supplier, get_supplier_financials
from .testing import WithPaymentTablesMixin


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


class SupplierFinancialsTests(WithPaymentTablesMixin, TestCase):
    """
    get_supplier_financials drives the /balance/ action and the detail
    serializer's outstanding_balance. The payments/payment_allocations
    tables are unmanaged reflections, so this class materializes them in
    the ephemeral test DB via WithPaymentTablesMixin (same trick as
    users.testing.WithUsersTableMixin).
    """

    def setUp(self):
        self.supplier = Supplier.objects.create(name="ACME Building Supplies")

    def test_balance_excludes_draft_and_cancelled_invoices(self):
        sent = SupplierInvoice.objects.create(
            supplier=self.supplier, invoice_number="SI-1", invoice_date="2026-08-01",
            total_amount=Decimal("1000.00"), status=SupplierInvoice.Status.SENT,
        )
        SupplierInvoice.objects.create(
            supplier=self.supplier, invoice_number="SI-2", invoice_date="2026-08-02",
            total_amount=Decimal("500.00"), status=SupplierInvoice.Status.DRAFT,
        )
        SupplierInvoice.objects.create(
            supplier=self.supplier, invoice_number="SI-3", invoice_date="2026-08-03",
            total_amount=Decimal("250.00"), status=SupplierInvoice.Status.CANCELLED,
        )
        PaymentAllocation.objects.create(
            payment_id=uuid.uuid4(), supplier_invoice_id=sent.id, allocated_amount=Decimal("400.00"),
        )

        financials = get_supplier_financials(self.supplier.id)
        self.assertEqual(financials["total_invoiced"], Decimal("1000.00"))
        self.assertEqual(financials["total_paid"], Decimal("400.00"))
        self.assertEqual(financials["outstanding_balance"], Decimal("600.00"))

    def test_balance_sums_allocations_across_multiple_invoices(self):
        first = SupplierInvoice.objects.create(
            supplier=self.supplier, invoice_number="SI-4", invoice_date="2026-08-04",
            total_amount=Decimal("800.00"), status=SupplierInvoice.Status.SENT,
        )
        second = SupplierInvoice.objects.create(
            supplier=self.supplier, invoice_number="SI-5", invoice_date="2026-08-05",
            total_amount=Decimal("200.00"), status=SupplierInvoice.Status.SENT,
        )
        PaymentAllocation.objects.create(
            payment_id=uuid.uuid4(), supplier_invoice_id=first.id, allocated_amount=Decimal("300.00"),
        )
        PaymentAllocation.objects.create(
            payment_id=uuid.uuid4(), supplier_invoice_id=second.id, allocated_amount=Decimal("200.00"),
        )

        financials = get_supplier_financials(self.supplier.id)
        self.assertEqual(financials["total_invoiced"], Decimal("1000.00"))
        self.assertEqual(financials["total_paid"], Decimal("500.00"))
        self.assertEqual(financials["outstanding_balance"], Decimal("500.00"))

    def test_balance_is_zero_when_no_activity(self):
        financials = get_supplier_financials(self.supplier.id)
        self.assertEqual(financials["total_invoiced"], Decimal("0.00"))
        self.assertEqual(financials["total_paid"], Decimal("0.00"))
        self.assertEqual(financials["outstanding_balance"], Decimal("0.00"))


class SupplierAPITestBase(WithUsersTableMixin, WithPaymentTablesMixin, TestCase):
    """Shared fixtures: a supplier, an internal creator user, an authed API client."""

    def setUp(self):
        self.supplier = Supplier.objects.create(name="ACME Building Supplies")
        self.creator = User.objects.create(
            username="creator", email="creator@example.com", password_hash="x",
            first_name="C", last_name="R", role="owner",
        )
        self.django_user = DjangoUser.objects.create_user(username="apitester", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(user=self.django_user)


class SupplierAPIListCreateTests(SupplierAPITestBase):
    def test_unauthenticated_request_is_blocked(self):
        anonymous = APIClient()
        response = anonymous.get("/api/suppliers/suppliers/")
        self.assertEqual(response.status_code, 403)

    def test_create_supplier(self):
        response = self.client.post("/api/suppliers/suppliers/", {
            "name": "SteelWorks LLC", "email": "sales@steelworks.example", "payment_terms": "Net 30",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "SteelWorks LLC")
        self.assertEqual(data["payment_terms"], "Net 30")
        self.assertTrue(data["is_active"])

    def test_list_returns_paginated_suppliers(self):
        response = self.client.get("/api/suppliers/suppliers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["name"], "ACME Building Supplies")

    def test_detail_includes_currency_and_balance(self):
        response = self.client.get(f"/api/suppliers/suppliers/{self.supplier.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["outstanding_balance"], "0.00")

    def test_update_supplier_payment_terms(self):
        response = self.client.patch(
            f"/api/suppliers/suppliers/{self.supplier.id}/",
            {"payment_terms": "Net 60"}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment_terms"], "Net 60")


class SupplierDetailActionsTests(SupplierAPITestBase):
    def test_purchase_orders_action(self):
        PurchaseOrder.objects.create(
            supplier=self.supplier, po_number="PO-100", order_date="2026-08-31", created_by=self.creator,
        )
        response = self.client.get(f"/api/suppliers/suppliers/{self.supplier.id}/purchase_orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([po["po_number"] for po in response.json()], ["PO-100"])

    def test_invoices_action(self):
        SupplierInvoice.objects.create(
            supplier=self.supplier, invoice_number="SI-API-1", invoice_date="2026-08-20",
            total_amount=Decimal("750.00"), status=SupplierInvoice.Status.SENT,
        )
        response = self.client.get(f"/api/suppliers/suppliers/{self.supplier.id}/invoices/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["invoice_number"], "SI-API-1")

    def test_payments_action_only_returns_outgoing(self):
        ClientPayment.objects.create(
            payment_number="PMT-OUT", payment_date="2026-08-25", amount=Decimal("400.00"),
            direction="OUTGOING", payment_method="BANK_TRANSFER", supplier_id=self.supplier.id,
        )
        ClientPayment.objects.create(
            payment_number="PMT-IN", payment_date="2026-08-26", amount=Decimal("9000.00"),
            direction="INCOMING", payment_method="CHECK", client_id=uuid.uuid4(),
        )
        response = self.client.get(f"/api/suppliers/suppliers/{self.supplier.id}/payments/")
        self.assertEqual(response.status_code, 200)
        numbers = [payment["payment_number"] for payment in response.json()]
        self.assertEqual(numbers, ["PMT-OUT"])

    def test_receipts_action_links_through_payments(self):
        payment = ClientPayment.objects.create(
            payment_number="PMT-REC", payment_date="2026-08-25", amount=Decimal("400.00"),
            direction="OUTGOING", payment_method="BANK_TRANSFER", supplier_id=self.supplier.id,
        )
        ReceiptSummary.objects.create(
            payment_id=payment.id, receipt_number="RCPT-1", receipt_date="2026-08-25",
            amount=Decimal("400.00"),
        )
        response = self.client.get(f"/api/suppliers/suppliers/{self.supplier.id}/receipts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["receipt_number"], "RCPT-1")

    def test_balance_action(self):
        invoice = SupplierInvoice.objects.create(
            supplier=self.supplier, invoice_number="SI-API-2", invoice_date="2026-08-20",
            total_amount=Decimal("1000.00"), status=SupplierInvoice.Status.SENT,
        )
        PaymentAllocation.objects.create(
            payment_id=uuid.uuid4(), supplier_invoice_id=invoice.id, allocated_amount=Decimal("300.00"),
        )
        response = self.client.get(f"/api/suppliers/suppliers/{self.supplier.id}/balance/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["total_invoiced"], "1000.00")
        self.assertEqual(data["total_paid"], "300.00")
        self.assertEqual(data["outstanding_balance"], "700.00")


class SupplierPageRenderTests(TestCase):
    """The dashboard Suppliers page is server-rendered HTML + client-side JS
    that speaks to the /api/suppliers API. These tests confirm the page
    renders and the view is auth-protected; the JS itself is exercised in
    the browser against the API endpoints (covered by the API tests above)."""

    def test_page_requires_login(self):
        response = self.client.get("/suppliers/")
        self.assertEqual(response.status_code, 302)  # redirect to login

    def test_page_renders_for_authenticated_user(self):
        user = DjangoUser.objects.create_user(username="owner", password="pass12345")
        self.client.force_login(user)
        response = self.client.get("/suppliers/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Suppliers", content)
        self.assertIn("suppliers.js", content)
        self.assertIn("data-supplier-rows", content)