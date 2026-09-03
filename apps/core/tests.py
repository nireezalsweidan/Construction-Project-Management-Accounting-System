"""
Tests for the ``core`` app -- Receipts page and the ``app_user`` bridge
(CPMAS-58).

Organized into:
- Page tests: the new /receipts/ view renders for an authenticated
  session and redirects an anonymous one, same pattern as the existing
  Suppliers page.
- Context processor tests: construction.context_processors.app_user's
  three cases -- anonymous (no bridge), a matching users.User by
  username (bridged), and no matching row (degrades to None rather
  than erroring).
"""
from django.contrib.auth.models import User as DjangoUser
from django.test import RequestFactory, TestCase

from construction.context_processors import app_user
from users.models import User as AppUser
from users.testing import WithUsersTableMixin


class ReceiptsPageRenderTests(TestCase):
    def test_redirects_anonymous_user_to_login(self):
        response = self.client.get("/receipts/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_page_renders_for_authenticated_user(self):
        DjangoUser.objects.create_user(username="apitester_core", password="pass12345")
        self.client.login(username="apitester_core", password="pass12345")
        response = self.client.get("/receipts/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/receipts.html")


class PaymentsPageRenderTests(TestCase):
    """The Payments dashboard page hosts the Receipt history register whose
    'View / PDF' action opens an in-app receipt preview dialog (rather than
    a browser confirm) and offers a Download PDF link."""

    def test_redirects_anonymous_user_to_login(self):
        response = self.client.get("/payments/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_page_renders_for_authenticated_user(self):
        DjangoUser.objects.create_user(username="apitester_payments", password="pass12345")
        self.client.login(username="apitester_payments", password="pass12345")
        response = self.client.get("/payments/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Receipt history", content)
        self.assertIn("data-inline-receipt-rows", content)

    def test_receipt_preview_dialog_is_present(self):
        DjangoUser.objects.create_user(username="apitester_payments2", password="pass12345")
        self.client.login(username="apitester_payments2", password="pass12345")
        response = self.client.get("/payments/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("data-receipt-preview-dialog", content)
        self.assertIn("data-receipt-preview-download", content)
        self.assertIn("data-receipt-preview-details", content)


class PartnersPageRenderTests(TestCase):
    """The Clients & Partners dashboard page is server-rendered HTML whose
    table and metrics are filled at runtime by partners.js from the
    /api/clients/, /api/suppliers/ and /api/contractors/ endpoints."""

    def test_redirects_anonymous_user_to_login(self):
        response = self.client.get("/partners/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_page_renders_for_authenticated_user(self):
        DjangoUser.objects.create_user(username="apitester_partners", password="pass12345")
        self.client.login(username="apitester_partners", password="pass12345")
        response = self.client.get("/partners/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Clients &amp; partners", content)
        self.assertIn("partners.js", content)
        self.assertIn("partners.css", content)
        self.assertIn("data-partner-rows", content)
        self.assertIn("partner-search-input", content)


class WorkforcePageRenderTests(TestCase):
    """The Workforce dashboard page is server-rendered HTML whose table and
    metrics are filled at runtime by workforce.js from the /api/employees/
    endpoint (and each employee's project assignments)."""

    def test_redirects_anonymous_user_to_login(self):
        response = self.client.get("/workforce/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_page_renders_for_authenticated_user(self):
        DjangoUser.objects.create_user(username="apitester_workforce", password="pass12345")
        self.client.login(username="apitester_workforce", password="pass12345")
        response = self.client.get("/workforce/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Workforce", content)
        self.assertIn("workforce.js", content)
        self.assertIn("workforce.css", content)
        self.assertIn("data-workforce-rows", content)
        self.assertIn("workforce-search-input", content)


class ProcurementPageRenderTests(TestCase):
    """The Procurement dashboard page is server-rendered HTML whose purchase
    order / goods receiving tables and metrics are filled at runtime by
    procurement.js from the /api/purchasing/ and /api/inventory/ endpoints.
    Receiving is append-only: the page exposes no edit/delete UI and issues
    no PATCH/PUT/DELETE for goods receipts."""

    def test_redirects_anonymous_user_to_login(self):
        response = self.client.get("/procurement/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_page_renders_for_authenticated_user(self):
        DjangoUser.objects.create_user(username="apitester_procurement", password="pass12345")
        self.client.login(username="apitester_procurement", password="pass12345")
        response = self.client.get("/procurement/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Procurement", content)
        self.assertIn("procurement.js", content)
        self.assertIn("procurement.css", content)
        self.assertIn("data-po-rows", content)
        self.assertIn("data-receipt-rows", content)
        self.assertIn("data-receive-dialog", content)
        self.assertIn("data-receipt-detail-dialog", content)
        self.assertIn("data-receive-po-select", content)
        self.assertNotIn("purchase_orders", content)


class AccountingPageRenderTests(TestCase):
    """The Accounting / Financial Transactions dashboard page is
    server-rendered HTML whose journal table and metrics are filled at
    runtime by accounting.js from the /api/accounting/ endpoints
    (AccountViewSet, FinancialTransactionViewSet, TransactionLineViewSet).
    The page is frontend-only against the existing backend: no models,
    serializers, or viewsets are modified."""

    def test_redirects_anonymous_user_to_login(self):
        response = self.client.get("/accounting/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_page_renders_for_authenticated_user(self):
        DjangoUser.objects.create_user(username="apitester_accounting", password="pass12345")
        self.client.login(username="apitester_accounting", password="pass12345")
        response = self.client.get("/accounting/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Accounting", content)
        self.assertIn("accounting.js", content)
        self.assertIn("accounting.css", content)
        self.assertIn("data-transaction-rows", content)
        self.assertIn("data-open-create", content)
        self.assertIn("data-txn-dialog", content)
        self.assertIn("data-detail-dialog", content)
        self.assertIn("data-metric", content)

    def test_sidebar_contains_accounting_link(self):
        DjangoUser.objects.create_user(username="apitester_accounting2", password="pass12345")
        self.client.login(username="apitester_accounting2", password="pass12345")
        response = self.client.get("/accounting/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("href=\"/accounting/\"", content)
        self.assertIn(">Accounting</span>", content)


class ReportsPageRenderTests(TestCase):
    """The Reports / Decision Intelligence dashboard page is server-rendered
    HTML whose report panels, stat cards, P&L, trend chart, aging buckets,
    budget table, and transaction ledger are filled at runtime by reports.js
    from the /api/accounting/reports/, /api/clients/clients/aging/, and
    /api/projects/budgets/portfolio-summary/ endpoints."""

    def test_redirects_anonymous_user_to_login(self):
        response = self.client.get("/reports/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_page_renders_for_authenticated_user(self):
        DjangoUser.objects.create_user(username="apitester_reports", password="pass12345")
        self.client.login(username="apitester_reports", password="pass12345")
        response = self.client.get("/reports/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Reports", content)
        self.assertIn("reports.js", content)
        self.assertIn("reports.css", content)
        self.assertIn("data-metric", content)
        self.assertIn("data-report-nav", content)

    def test_sidebar_contains_reports_link(self):
        DjangoUser.objects.create_user(username="apitester_reports2", password="pass12345")
        self.client.login(username="apitester_reports2", password="pass12345")
        response = self.client.get("/reports/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("href=\"/reports/\"", content)
        self.assertIn(">Reports</span>", content)


class AppUserContextProcessorTests(WithUsersTableMixin, TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_anonymous_request_has_no_bridge(self):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/")
        request.user = AnonymousUser()
        self.assertEqual(app_user(request), {"app_user_id": None})

    def test_authenticated_with_no_matching_users_user_degrades_to_none(self):
        django_user = DjangoUser.objects.create_user(username="unmatched", password="pass12345")
        request = self.factory.get("/")
        request.user = django_user
        self.assertEqual(app_user(request), {"app_user_id": None})

    def test_authenticated_with_matching_username_is_bridged(self):
        django_user = DjangoUser.objects.create_user(username="bridged.user", password="pass12345")
        app_user_row = AppUser.objects.create(
            username="bridged.user", email="bridged@example.com", password_hash="x",
            first_name="B", last_name="U", role="OWNER",
        )
        request = self.factory.get("/")
        request.user = django_user
        self.assertEqual(app_user(request), {"app_user_id": str(app_user_row.id)})
