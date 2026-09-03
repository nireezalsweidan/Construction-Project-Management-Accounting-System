from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from rest_framework.test import APIClient

from invoicing.models import ClientInvoice
from projects.testing import WithProjectsTableMixin

from .models import Client, ClientInvoiceSummary
from .testing import WithClientsTableMixin


class ClientModelTests(TestCase):
    """
    Model-level tests only — no .save()/.objects.create() calls, because
    Client (and every model in this app) is managed=False: the test runner
    doesn't create these tables in the ephemeral test database, only real
    Postgres/Supabase has them.

    get_client_financials() does real aggregate queries and can't be unit
    tested against SQLite for that reason. Covering it needs either:
      (a) pointing TEST DATABASES at a disposable Supabase/Postgres schema, or
      (b) an integration test run manually against a seeded dev DB.
    Flagging this as a team decision rather than solving it here.
    """

    def test_str_prefers_company_name(self):
        client = Client(name="John Doe", company_name="Doe Holdings")
        self.assertEqual(str(client), "Doe Holdings")

    def test_str_falls_back_to_name(self):
        client = Client(name="John Doe", company_name=None)
        self.assertEqual(str(client), "John Doe")

    def test_invoice_status_choices_match_db_enum(self):
        # Guards against the model's choices drifting from
        # invoice_status_enum in construction_management_supabase.sql.
        expected = {"DRAFT", "SENT", "PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED"}
        actual = {value for value, _ in ClientInvoiceSummary.STATUS_CHOICES}
        self.assertEqual(expected, actual)


class ReceivablesAgingAPITests(WithClientsTableMixin, WithProjectsTableMixin, TestCase):
    """
    The Receivables aging endpoint (/api/clients/clients/aging/) reads the
    real ClientInvoice + PaymentAllocation tables (managed=True, so they
    exist in the test DB) but also joins Client/Project (managed=False) --
    those are brought up via the mixins.
    """

    def setUp(self):
        from projects.models import Project

        super().setUp()
        self.client_entity = Client.objects.create(name="Acme Corp")
        self.project = Project.objects.create(
            code="PRJ-1", name="Tower A", project_type="WHOLE_BUILDING",
            start_date="2026-01-01", contract_value=Decimal("100000"),
        )
        self.django_user = DjangoUser.objects.create_user(username="agingtester", password="pass12345")
        self.api = APIClient()
        self.api.force_authenticate(user=self.django_user)

    def _make_invoice(self, number, days_overdue, amount="1000.00"):
        return ClientInvoice.objects.create(
            invoice_number=number,
            client=self.client_entity,
            project=self.project,
            total_amount=Decimal(amount),
            invoice_date=date.today() - timedelta(days=days_overdue),
            due_date=date.today() - timedelta(days=days_overdue),
            status=ClientInvoice.Status.SENT,
        )

    def test_anonymous_is_rejected(self):
        response = APIClient().get("/api/clients/clients/aging/")
        self.assertEqual(response.status_code, 401)

    def test_buckets_outstanding_invoices(self):
        self._make_invoice("INV-10", days_overdue=10)    # current (0-30)
        self._make_invoice("INV-45", days_overdue=45)    # 31-60
        self._make_invoice("INV-75", days_overdue=75)    # 61-90
        self._make_invoice("INV-120", days_overdue=120)  # 90+

        response = self.api.get("/api/clients/clients/aging/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_outstanding"], "4000.00")
        by_bucket = {b["bucket"]: b for b in data["buckets"]}
        self.assertEqual(by_bucket["current"]["total"], 1000.0)
        self.assertEqual(by_bucket["overdue_31_60"]["total"], 1000.0)
        self.assertEqual(by_bucket["overdue_61_90"]["total"], 1000.0)
        self.assertEqual(by_bucket["overdue_90_plus"]["total"], 1000.0)

    def test_empty_when_no_invoices(self):
        response = self.api.get("/api/clients/clients/aging/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_outstanding"], "0.00")
        self.assertTrue(all(b["invoices"] == [] for b in data["buckets"]))