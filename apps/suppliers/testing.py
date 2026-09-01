"""
Test-only utility for the ``suppliers`` app.

``payments``, ``payment_allocations`` and ``receipts`` are all
``managed = False`` (read-mostly reflections of tables that already exist
in the live Supabase DB -- see ``clients.models.ClientPayment``,
``clients.models.PaymentAllocation`` and ``suppliers.models.ReceiptSummary``),
so Django's normal migration/test-database setup never creates those tables
against a fresh, empty test database. Any test that needs to exercise the
supplier financials (outstanding balance math, payments/receipts listing)
has to materialize them for the duration of that test class.

Same technique and reasoning as ``users.testing.WithUsersTableMixin``: the
tables are created via the schema editor before Django's ``TestCase`` wraps
the class in its own transaction, and dropped again after that wrapping
closes.
"""
from django.db import connection

from clients.models import ClientPayment, PaymentAllocation
from suppliers.models import ReceiptSummary


class WithPaymentTablesMixin:
    """
    Mix into any Django TestCase subclass that needs the payments,
    payment_allocations and receipts tables to exist (e.g. to seed a
    supplier's payment/allocation/receipt rows or call
    ``get_supplier_financials``).

    Usage: ``class MyTests(WithPaymentTablesMixin, TestCase): ...`` --
    WithPaymentTablesMixin must come before TestCase in the MRO so its
    setUpClass/tearDownClass wrap (not get wrapped by) TestCase's own.
    """

    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            editor.create_model(ClientPayment)
            editor.create_model(PaymentAllocation)
            editor.create_model(ReceiptSummary)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            editor.delete_model(ClientPayment)
            editor.delete_model(PaymentAllocation)
            editor.delete_model(ReceiptSummary)