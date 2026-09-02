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
