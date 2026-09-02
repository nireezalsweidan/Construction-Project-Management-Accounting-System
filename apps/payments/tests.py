"""
Tests for the ``payments`` app -- Accounts Receivable & Accounts
Payable slice (CPMAS-35).

Organized into:
- Service tests: outstanding_balance (DRAFT/CANCELLED short-circuit,
  balance reduction after allocation) and allocate_payment (the core
  direction-matching, invoice-status, and over-allocation guards).
- API tests: the same behaviors through the real DRF endpoints --
  append-only enforcement (no update/destroy routes), receipt
  direction validation, and the payment_allocations CHECK-constraint
  mirror.
"""
from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from clients.models import Client
from clients.testing import WithClientsTableMixin
from invoicing.models import ClientInvoice, SupplierInvoice
from projects.testing import WithProjectsTableMixin
from suppliers.models import Supplier
from users.models import User
from users.testing import WithUsersTableMixin

from .models import Payment, PaymentAllocation, Receipt
from .services import allocate_payment, outstanding_balance, unallocated_amount


class PaymentsTestBase(WithUsersTableMixin, WithClientsTableMixin, WithProjectsTableMixin, TestCase):
    """
    Shared fixtures: a client, a supplier, a creator user, and SENT
    invoices on both sides.

    Mixes in WithProjectsTableMixin too: ClientInvoice.project is a
    nullable FK into projects -- under SQLite, an FK column's target
    table must exist at INSERT time even when the value is NULL (same
    quirk documented on accounting.tests.AccountingTestBase).
    """

    def setUp(self):
        self.creator = User.objects.create(
            username="creator", email="creator@example.com", password_hash="x",
            first_name="C", last_name="R", role="accountant",
        )
        self.client_obj = Client.objects.create(name="Jane Homeowner")
        self.supplier = Supplier.objects.create(name="ACME Building Supplies")

    def make_client_invoice(self, total_amount=Decimal("1000.00"), status=ClientInvoice.Status.SENT, **kwargs):
        defaults = dict(
            client=self.client_obj, invoice_number="CINV-0001", invoice_date="2026-08-31",
            total_amount=total_amount, status=status,
        )
        defaults.update(kwargs)
        return ClientInvoice.objects.create(**defaults)

    def make_supplier_invoice(self, total_amount=Decimal("500.00"), status=SupplierInvoice.Status.SENT, **kwargs):
        defaults = dict(
            supplier=self.supplier, invoice_number="SINV-0001", invoice_date="2026-08-31",
            total_amount=total_amount, status=status,
        )
        defaults.update(kwargs)
        return SupplierInvoice.objects.create(**defaults)

    def make_payment(self, direction=Payment.Direction.INCOMING, amount=Decimal("1000.00"), **kwargs):
        defaults = dict(
            payment_number="PMT-0001", payment_date="2026-08-31", amount=amount,
            direction=direction, payment_method="bank_transfer", created_by=self.creator,
        )
        if direction == Payment.Direction.INCOMING:
            defaults.setdefault('client', self.client_obj)
        else:
            defaults.setdefault('supplier', self.supplier)
        defaults.update(kwargs)
        return Payment.objects.create(**defaults)


class OutstandingBalanceTests(PaymentsTestBase):
    def test_draft_invoice_has_zero_balance(self):
        invoice = self.make_client_invoice(status=ClientInvoice.Status.DRAFT)
        self.assertEqual(outstanding_balance(invoice), Decimal("0.00"))

    def test_cancelled_invoice_has_zero_balance(self):
        invoice = self.make_client_invoice(status=ClientInvoice.Status.CANCELLED)
        self.assertEqual(outstanding_balance(invoice), Decimal("0.00"))

    def test_sent_invoice_with_no_allocations_equals_total(self):
        invoice = self.make_client_invoice(total_amount=Decimal("750.00"))
        self.assertEqual(outstanding_balance(invoice), Decimal("750.00"))

    def test_balance_reduces_after_allocation(self):
        invoice = self.make_client_invoice(total_amount=Decimal("1000.00"))
        payment = self.make_payment(amount=Decimal("1000.00"))
        allocate_payment(payment, invoice, Decimal("400.00"))
        self.assertEqual(outstanding_balance(invoice), Decimal("600.00"))

    def test_works_for_supplier_invoice_too(self):
        invoice = self.make_supplier_invoice(total_amount=Decimal("500.00"))
        self.assertEqual(outstanding_balance(invoice), Decimal("500.00"))


class UnallocatedAmountTests(PaymentsTestBase):
    def test_equals_full_amount_with_no_allocations(self):
        payment = self.make_payment(amount=Decimal("1000.00"))
        self.assertEqual(unallocated_amount(payment), Decimal("1000.00"))

    def test_reduces_after_allocation(self):
        invoice = self.make_client_invoice(total_amount=Decimal("1000.00"))
        payment = self.make_payment(amount=Decimal("1000.00"))
        allocate_payment(payment, invoice, Decimal("300.00"))
        self.assertEqual(unallocated_amount(payment), Decimal("700.00"))


class AllocatePaymentServiceTests(PaymentsTestBase):
    def test_partial_allocation_marks_client_invoice_partially_paid(self):
        invoice = self.make_client_invoice(total_amount=Decimal("1000.00"))
        payment = self.make_payment(amount=Decimal("1000.00"))
        allocate_payment(payment, invoice, Decimal("400.00"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, ClientInvoice.Status.PARTIALLY_PAID)

    def test_full_allocation_marks_client_invoice_paid(self):
        invoice = self.make_client_invoice(total_amount=Decimal("1000.00"))
        payment = self.make_payment(amount=Decimal("1000.00"))
        allocate_payment(payment, invoice, Decimal("1000.00"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, ClientInvoice.Status.PAID)

    def test_full_allocation_marks_supplier_invoice_paid(self):
        invoice = self.make_supplier_invoice(total_amount=Decimal("500.00"))
        payment = self.make_payment(direction=Payment.Direction.OUTGOING, amount=Decimal("500.00"))
        allocate_payment(payment, invoice, Decimal("500.00"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, SupplierInvoice.Status.PAID)

    def test_outgoing_payment_cannot_fund_a_client_invoice(self):
        invoice = self.make_client_invoice()
        payment = self.make_payment(direction=Payment.Direction.OUTGOING, amount=Decimal("1000.00"))
        with self.assertRaises(ValidationError):
            allocate_payment(payment, invoice, Decimal("100.00"))

    def test_incoming_payment_cannot_fund_a_supplier_invoice(self):
        invoice = self.make_supplier_invoice()
        payment = self.make_payment(direction=Payment.Direction.INCOMING, amount=Decimal("1000.00"))
        with self.assertRaises(ValidationError):
            allocate_payment(payment, invoice, Decimal("100.00"))

    def test_cannot_allocate_to_a_draft_invoice(self):
        invoice = self.make_client_invoice(status=ClientInvoice.Status.DRAFT)
        payment = self.make_payment(amount=Decimal("1000.00"))
        with self.assertRaises(ValidationError):
            allocate_payment(payment, invoice, Decimal("100.00"))

    def test_cannot_exceed_invoice_outstanding_balance(self):
        invoice = self.make_client_invoice(total_amount=Decimal("100.00"))
        payment = self.make_payment(amount=Decimal("1000.00"))
        with self.assertRaises(ValidationError):
            allocate_payment(payment, invoice, Decimal("150.00"))

    def test_cannot_exceed_payment_unallocated_amount(self):
        invoice = self.make_client_invoice(total_amount=Decimal("1000.00"))
        payment = self.make_payment(amount=Decimal("100.00"))
        with self.assertRaises(ValidationError):
            allocate_payment(payment, invoice, Decimal("150.00"))

    def test_second_allocation_after_first_still_respects_remaining_balance(self):
        invoice = self.make_client_invoice(total_amount=Decimal("1000.00"))
        payment = self.make_payment(amount=Decimal("1000.00"))
        allocate_payment(payment, invoice, Decimal("600.00"))
        with self.assertRaises(ValidationError):
            allocate_payment(payment, invoice, Decimal("500.00"))  # only 400 left on the invoice


class PaymentAPITests(PaymentsTestBase):
    def setUp(self):
        super().setUp()
        django_user = DjangoUser.objects.create_user(username="apitester3", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(user=django_user)

    def test_create_incoming_payment_via_api(self):
        response = self.client.post("/api/payments/payments/", {
            "payment_number": "PMT-API-1", "payment_date": "2026-08-31", "amount": "1000.00",
            "direction": "INCOMING", "payment_method": "bank_transfer",
            "client": str(self.client_obj.id), "created_by": str(self.creator.id),
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["unallocated_amount"], "1000.00")

    def test_incoming_payment_without_client_is_rejected(self):
        response = self.client.post("/api/payments/payments/", {
            "payment_number": "PMT-API-2", "payment_date": "2026-08-31", "amount": "1000.00",
            "direction": "INCOMING", "payment_method": "bank_transfer", "created_by": str(self.creator.id),
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_payment_has_no_update_or_delete_routes(self):
        payment = self.make_payment(amount=Decimal("1000.00"))
        response = self.client.patch(f"/api/payments/payments/{payment.id}/", {"amount": "1.00"}, format="json")
        self.assertEqual(response.status_code, 405)
        response = self.client.delete(f"/api/payments/payments/{payment.id}/")
        self.assertEqual(response.status_code, 405)

    def test_allocate_payment_via_api_updates_invoice_status(self):
        invoice = self.make_client_invoice(total_amount=Decimal("1000.00"))
        payment = self.make_payment(amount=Decimal("1000.00"))

        response = self.client.post("/api/payments/payment-allocations/", {
            "payment": str(payment.id), "client_invoice": str(invoice.id), "allocated_amount": "1000.00",
        }, format="json")
        self.assertEqual(response.status_code, 201)

        invoice_response = self.client.get(f"/api/invoicing/client-invoices/{invoice.id}/")
        self.assertEqual(invoice_response.json()["status"], "PAID")
        self.assertEqual(invoice_response.json()["outstanding_balance"], "0.00")

    def test_allocation_rejects_both_invoice_fields_set(self):
        client_invoice = self.make_client_invoice()
        supplier_invoice = self.make_supplier_invoice()
        payment = self.make_payment(amount=Decimal("1000.00"))

        response = self.client.post("/api/payments/payment-allocations/", {
            "payment": str(payment.id), "client_invoice": str(client_invoice.id),
            "supplier_invoice": str(supplier_invoice.id), "allocated_amount": "100.00",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_allocation_rejects_neither_invoice_field_set(self):
        payment = self.make_payment(amount=Decimal("1000.00"))
        response = self.client.post("/api/payments/payment-allocations/", {
            "payment": str(payment.id), "allocated_amount": "100.00",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_allocation_over_invoice_balance_returns_400(self):
        invoice = self.make_client_invoice(total_amount=Decimal("100.00"))
        payment = self.make_payment(amount=Decimal("1000.00"))
        response = self.client.post("/api/payments/payment-allocations/", {
            "payment": str(payment.id), "client_invoice": str(invoice.id), "allocated_amount": "150.00",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_receipt_creation_for_incoming_payment(self):
        payment = self.make_payment(amount=Decimal("1000.00"))
        response = self.client.post("/api/payments/receipts/", {
            "payment": str(payment.id), "receipt_number": "RCPT-0001",
            "receipt_date": "2026-08-31", "amount": "1000.00",
        }, format="json")
        self.assertEqual(response.status_code, 201)

    def test_receipt_rejected_for_outgoing_payment(self):
        payment = self.make_payment(direction=Payment.Direction.OUTGOING, amount=Decimal("500.00"))
        response = self.client.post("/api/payments/receipts/", {
            "payment": str(payment.id), "receipt_number": "RCPT-0002",
            "receipt_date": "2026-08-31", "amount": "500.00",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_receipt_rejected_if_payment_already_has_one(self):
        payment = self.make_payment(amount=Decimal("1000.00"))
        Receipt.objects.create(payment=payment, receipt_number="RCPT-0003", receipt_date="2026-08-31", amount=Decimal("1000.00"))
        response = self.client.post("/api/payments/receipts/", {
            "payment": str(payment.id), "receipt_number": "RCPT-0004",
            "receipt_date": "2026-08-31", "amount": "1000.00",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_anonymous_request_is_rejected(self):
        anon = APIClient()
        response = anon.get("/api/payments/payments/")
        # 401 (not 403): with the auth ticket in place, unauthenticated
        # requests are challenged to authenticate before access is denied.
        self.assertEqual(response.status_code, 401)


class ReceiptDetailAndDownloadAPITests(PaymentsTestBase):
    """
    CPMAS-21 (BRD 5.19): the receipt fields it lists beyond what the
    Receipt model itself stores (client/supplier, payment method), the
    printable/downloadable PDF endpoint, and filtering by client/
    supplier/payment.
    """

    def setUp(self):
        super().setUp()
        django_user = DjangoUser.objects.create_user(username="apitester4", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(user=django_user)

    def make_receipt(self, **kwargs):
        payment = self.make_payment(amount=Decimal("1000.00"))
        defaults = dict(payment=payment, receipt_number="RCPT-DL-1", receipt_date="2026-08-31", amount=Decimal("1000.00"))
        defaults.update(kwargs)
        return Receipt.objects.create(**defaults)

    def test_receipt_response_includes_client_and_payment_method(self):
        receipt = self.make_receipt()
        response = self.client.get(f"/api/payments/receipts/{receipt.id}/")
        data = response.json()
        self.assertEqual(data["client_name"], "Jane Homeowner")
        self.assertIsNone(data["supplier_name"])
        self.assertEqual(data["payment_method"], "bank_transfer")

    def test_download_returns_a_pdf_attachment(self):
        receipt = self.make_receipt(receipt_number="RCPT-DL-2")
        response = self.client.get(f"/api/payments/receipts/{receipt.id}/download/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('attachment; filename="RCPT-DL-2.pdf"', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_filter_by_client(self):
        receipt = self.make_receipt(receipt_number="RCPT-DL-3")
        other_client = Client.objects.create(name="Someone Else")
        other_payment = self.make_payment(payment_number="PMT-OTHER", amount=Decimal("50.00"), client=other_client)
        Receipt.objects.create(payment=other_payment, receipt_number="RCPT-DL-4", receipt_date="2026-08-31", amount=Decimal("50.00"))

        response = self.client.get(f"/api/payments/receipts/?client={self.client_obj.id}")
        numbers = [r["receipt_number"] for r in response.json()["results"]]
        self.assertIn("RCPT-DL-3", numbers)
        self.assertNotIn("RCPT-DL-4", numbers)

    def test_filter_by_payment(self):
        receipt = self.make_receipt(receipt_number="RCPT-DL-5")
        response = self.client.get(f"/api/payments/receipts/?payment={receipt.payment_id}")
        numbers = [r["receipt_number"] for r in response.json()["results"]]
        self.assertEqual(numbers, ["RCPT-DL-5"])

    def test_anonymous_download_is_rejected(self):
        receipt = self.make_receipt(receipt_number="RCPT-DL-6")
        anon = APIClient()
        response = anon.get(f"/api/payments/receipts/{receipt.id}/download/")
        self.assertEqual(response.status_code, 401)
