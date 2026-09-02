"""
Tests for the ``suppliers`` app -- Supplier Management.

Two groups:
- model tests (the original CPMAS-28 set covering the Supplier record),
- Supplier Management API tests: CRUD, currency constant, and the
  purchase-orders / invoices / payments / balance detail actions.

Suppliers are pure data records: nothing here creates authentication,
login, or a role for them -- the API is exercised exactly like the rest of
the system, as a logged-in internal user (Django auth user + DRF
SessionAuthentication / IsAuthenticated).

Financial data reuses the ``payments`` app's managed models (Payment,
PaymentAllocation) -- those own the payments/payment_allocations tables and
create them in the ephemeral test DB via their own migrations. The only
table this suite still has to materialize by hand is ``users`` (managed=False
reflection) via users.testing.WithUsersTableMixin, needed because
Payment.created_by is a required FK to it.
"""
import time
import uuid
from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from rest_framework.test import APIClient

from clients.testing import WithClientsTableMixin
from invoicing.models import SupplierInvoice
from payments.models import Payment, PaymentAllocation
from purchasing.models import PurchaseOrder
from users.models import User
from users.testing import WithUsersTableMixin

from .models import Supplier, get_supplier_financials


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


class SupplierFinancialsTests(WithUsersTableMixin, WithClientsTableMixin, TestCase):
    """
    get_supplier_financials drives the /balance/ action and the detail
    serializer's outstanding_balance. Uses the payments app's managed models.
    """

    def setUp(self):
        self.supplier = Supplier.objects.create(name="ACME Building Supplies")
        self.creator = User.objects.create(
            username="creator", email="creator@example.com", password_hash="x",
            first_name="C", last_name="R", role="accountant",
        )

    def make_payment(self, direction=Payment.Direction.OUTGOING, **kwargs):
        defaults = dict(
            payment_number="PMT-%s" % uuid.uuid4().hex[:8], payment_date="2026-08-31",
            amount=Decimal("0.00"), direction=direction, payment_method="bank_transfer",
            created_by=self.creator,
        )
        if direction == Payment.Direction.OUTGOING:
            defaults["supplier"] = self.supplier
        else:
            defaults["client"] = None
        defaults.update(kwargs)
        return Payment.objects.create(**defaults)

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
        payment = self.make_payment(amount=Decimal("400.00"))
        PaymentAllocation.objects.create(
            payment=payment, supplier_invoice=sent, allocated_amount=Decimal("400.00"),
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
            payment=self.make_payment(amount=Decimal("300.00")),
            supplier_invoice=first, allocated_amount=Decimal("300.00"),
        )
        PaymentAllocation.objects.create(
            payment=self.make_payment(amount=Decimal("200.00")),
            supplier_invoice=second, allocated_amount=Decimal("200.00"),
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


class SupplierAPITestBase(WithUsersTableMixin, WithClientsTableMixin, TestCase):
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
        # 401 (not 403): with the auth ticket in place, unauthenticated
        # requests are challenged to authenticate before access is denied.
        self.assertEqual(response.status_code, 401)

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

    def test_filter_by_is_active(self):
        # CPMAS-23: this app previously had zero query-param filtering.
        inactive = Supplier.objects.create(name="Retired Vendor", is_active=False)

        active_response = self.client.get("/api/suppliers/suppliers/?is_active=true")
        active_names = [s["name"] for s in active_response.json()["results"]]
        self.assertIn("ACME Building Supplies", active_names)
        self.assertNotIn(inactive.name, active_names)

        inactive_response = self.client.get("/api/suppliers/suppliers/?is_active=false")
        inactive_names = [s["name"] for s in inactive_response.json()["results"]]
        self.assertEqual(inactive_names, [inactive.name])


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
        Payment.objects.create(
            payment_number="PMT-OUT", payment_date="2026-08-25", amount=Decimal("400.00"),
            direction=Payment.Direction.OUTGOING, payment_method="BANK_TRANSFER",
            supplier=self.supplier, created_by=self.creator,
        )
        # An INCOMING payment from a client must NOT appear on the supplier's
        # payments action, even though both share the same payments table.
        from clients.models import Client
        incoming_client = Client.objects.create(name="Jane Homeowner")
        Payment.objects.create(
            payment_number="PMT-IN", payment_date="2026-08-26", amount=Decimal("9000.00"),
            direction=Payment.Direction.INCOMING, payment_method="CHECK",
            client=incoming_client, created_by=self.creator,
        )
        response = self.client.get(f"/api/suppliers/suppliers/{self.supplier.id}/payments/")
        self.assertEqual(response.status_code, 200)
        numbers = [payment["payment_number"] for payment in response.json()]
        self.assertEqual(numbers, ["PMT-OUT"])

    def test_balance_action(self):
        invoice = SupplierInvoice.objects.create(
            supplier=self.supplier, invoice_number="SI-API-2", invoice_date="2026-08-20",
            total_amount=Decimal("1000.00"), status=SupplierInvoice.Status.SENT,
        )
        payment = Payment.objects.create(
            payment_number="PMT-BAL", payment_date="2026-08-25", amount=Decimal("300.00"),
            direction=Payment.Direction.OUTGOING, payment_method="BANK_TRANSFER",
            supplier=self.supplier, created_by=self.creator,
        )
        PaymentAllocation.objects.create(
            payment=payment, supplier_invoice=invoice, allocated_amount=Decimal("300.00"),
        )
        response = self.client.get(f"/api/suppliers/suppliers/{self.supplier.id}/balance/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["total_invoiced"], "1000.00")
        self.assertEqual(data["total_paid"], "300.00")
        self.assertEqual(data["outstanding_balance"], "700.00")


class SupplierSummaryTests(SupplierAPITestBase):
    """The dashboard page's stat cards are fed by a single /summary/ call."""

    def test_summary_empty_portfolio(self):
        response = self.client.get("/api/suppliers/suppliers/summary/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["total_suppliers"], 1)
        self.assertEqual(data["active_suppliers"], 1)
        self.assertEqual(data["total_invoiced"], "0.00")
        self.assertEqual(data["total_paid"], "0.00")
        self.assertEqual(data["outstanding_balance"], "0.00")

    def test_summary_aggregates_across_suppliers(self):
        acme_invoice = SupplierInvoice.objects.create(
            supplier=self.supplier, invoice_number="SI-1", invoice_date="2026-08-01",
            total_amount=Decimal("1000.00"), status=SupplierInvoice.Status.SENT,
        )
        SupplierInvoice.objects.create(
            supplier=self.supplier, invoice_number="SI-2", invoice_date="2026-08-02",
            total_amount=Decimal("500.00"), status=SupplierInvoice.Status.DRAFT,
        )
        supplier_two = Supplier.objects.create(name="Other Supplies", is_active=False)
        other_invoice = SupplierInvoice.objects.create(
            supplier=supplier_two, invoice_number="SI-3", invoice_date="2026-08-03",
            total_amount=Decimal("2000.00"), status=SupplierInvoice.Status.SENT,
        )
        acme_payment = Payment.objects.create(
            payment_number="PMT-A", payment_date="2026-08-10", amount=Decimal("400.00"),
            direction=Payment.Direction.OUTGOING, payment_method="BANK_TRANSFER",
            supplier=self.supplier, created_by=self.creator,
        )
        other_payment = Payment.objects.create(
            payment_number="PMT-B", payment_date="2026-08-11", amount=Decimal("1500.00"),
            direction=Payment.Direction.OUTGOING, payment_method="BANK_TRANSFER",
            supplier=supplier_two, created_by=self.creator,
        )
        PaymentAllocation.objects.create(
            payment=acme_payment, supplier_invoice=acme_invoice, allocated_amount=Decimal("400.00"),
        )
        PaymentAllocation.objects.create(
            payment=other_payment, supplier_invoice=other_invoice, allocated_amount=Decimal("1500.00"),
        )

        response = self.client.get("/api/suppliers/suppliers/summary/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_suppliers"], 2)
        self.assertEqual(data["active_suppliers"], 1)
        self.assertEqual(data["total_invoiced"], "3000.00")
        self.assertEqual(data["total_paid"], "1900.00")
        self.assertEqual(data["outstanding_balance"], "1100.00")


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
        self.assertIn("suppliers.css", content)
        self.assertIn("site-exact.css", content)
        self.assertIn("v3-fixes.css", content)
        self.assertIn("data-supplier-rows", content)
        self.assertIn("module-stat-grid", content)
        self.assertIn('data-metric="outstanding"', content)