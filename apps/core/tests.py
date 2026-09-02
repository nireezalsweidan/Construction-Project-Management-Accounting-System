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


class LoginPageTests(WithUsersTableMixin, TestCase):
    """End-to-end tests for the server-rendered login page + middleware."""

    def setUp(self):
        self.owner = AppUser.objects.create(
            username="owner", email="owner@example.com", password_hash="x",
            first_name="O", last_name="W", role="OWNER",
        )
        self.owner.set_password("owner-pass-123")
        self.owner.save(update_fields=["password_hash"])

    def test_login_page_renders(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        self.assertContains(response, "Username")

    def test_successful_login_redirects_and_grants_access(self):
        # Dashboard is @login_required -> anonymous is redirected first.
        protected = self.client.get("/dashboard/")
        self.assertEqual(protected.status_code, 302)
        self.assertIn("/accounts/login/", protected.url)

        response = self.client.post(
            "/accounts/login/",
            {"username": "owner", "password": "owner-pass-123"},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/dashboard/")

        # After login the @login_required dashboard is reachable.
        dashboard = self.client.get("/dashboard/")
        self.assertEqual(dashboard.status_code, 200)

    def test_invalid_login_shows_error_and_stays_logged_out(self):
        response = self.client.post(
            "/accounts/login/",
            {"username": "owner", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your username or password is incorrect.")
        # Still anonymous -> dashboard redirects to login.
        dashboard = self.client.get("/dashboard/")
        self.assertEqual(dashboard.status_code, 302)
        self.assertIn("/accounts/login/", dashboard.url)

    def test_logout_clears_session(self):
        self.client.post(
            "/accounts/login/",
            {"username": "owner", "password": "owner-pass-123"},
        )
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)
        self.client.post("/accounts/logout/")
        # After logout the dashboard redirects to login again.
        dashboard = self.client.get("/dashboard/")
        self.assertEqual(dashboard.status_code, 302)
        self.assertIn("/accounts/login/", dashboard.url)


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


class RoleRoutingTests(WithUsersTableMixin, TestCase):
    """Owner and accountant land on their role-appropriate dashboards, and
    workspace/operations pages are gated so accountants are redirected away."""

    def setUp(self):
        self.owner = AppUser.objects.create(
            username="owner", email="owner@example.com", password_hash="x",
            first_name="O", last_name="W", role="OWNER",
        )
        self.owner.set_password("owner-pass-123")
        self.owner.save(update_fields=["password_hash"])
        self.accountant = AppUser.objects.create(
            username="accountant", email="accountant@example.com", password_hash="x",
            first_name="A", last_name="C", role="ACCOUNTANT",
        )
        self.accountant.set_password("accountant-pass-123")
        self.accountant.save(update_fields=["password_hash"])

    def _login(self, username, password):
        self.client.post(
            "/accounts/login/", {"username": username, "password": password}, follow=False,
        )

    def test_owner_lands_on_owner_overview(self):
        self._login("owner", "owner-pass-123")
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/overview.html")

    def test_accountant_lands_on_finance_dashboard(self):
        self._login("accountant", "accountant-pass-123")
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/accountant_overview.html")

    def test_accountant_cannot_open_owner_workspace_page(self):
        self._login("accountant", "accountant-pass-123")
        response = self.client.get("/projects/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/dashboard/")

    def test_owner_can_open_workspace_page(self):
        self._login("owner", "owner-pass-123")
        response = self.client.get("/projects/")
        self.assertEqual(response.status_code, 200)

    def test_accountant_can_open_finance_page(self):
        self._login("accountant", "accountant-pass-123")
        response = self.client.get("/invoices/")
        self.assertEqual(response.status_code, 200)
