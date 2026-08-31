from django.test import TestCase

from .models import Client, ClientInvoiceSummary


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