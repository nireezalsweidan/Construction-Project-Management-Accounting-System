"""
Tests for the ``users`` app -- Authentication & Authorization (RBAC).

Covers:
- Service/model: password hashing (set_password/check_password), role flags,
  and the stateless reset-token generator.
- Auth API: login, logout, profile (get/patch), change-password.
- Password reset API: request (emails a reset link) and complete (reset
  with uid + token).
- RBAC: non-Owner users cannot reach Owner-only user management.

The in-memory SQLite test DB doesn't provision the (managed=False) users
table, so every test class mixes in ``WithUsersTableMixin`` to create it
for the duration of the class, mirroring the other domain apps.
"""
from django.core import mail
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient

from users.models import Role, User
from users.testing import WithUsersTableMixin
from users.tokens import default_token_generator


def _make_password():
    user = User(username="pw", email="pw@example.com", password_hash="x",
                first_name="P", last_name="W", role=Role.OWNER)
    user.set_password("correct-horse-battery-staple")
    user.save()
    return user


class PasswordHashingTests(WithUsersTableMixin, TestCase):
    def test_set_password_hashes_not_plaintext(self):
        user = _make_password()
        self.assertNotEqual(user.password_hash, "correct-horse-battery-staple")
        self.assertTrue(user.check_password("correct-horse-battery-staple"))
        self.assertFalse(user.check_password("wrong"))

    def test_role_flags(self):
        owner = _make_password()
        owner.role = Role.OWNER
        self.assertTrue(owner.is_owner)
        self.assertFalse(owner.is_accountant)
        owner.role = Role.ACCOUNTANT
        self.assertTrue(owner.is_accountant)
        self.assertFalse(owner.is_owner)


class AuthApiBase(WithUsersTableMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User(username="owner", email="owner@example.com",
                          first_name="O", last_name="W", role=Role.OWNER)
        self.owner.set_password("owner-pass-123")
        self.owner.save()
        self.acc = User(username="accountant", email="acc@example.com",
                        first_name="A", last_name="C", role=Role.ACCOUNTANT)
        self.acc.set_password("acc-pass-123")
        self.acc.save()

    def login(self, username, password):
        return self.client.post("/api/auth/login/",
                                {"username": username, "password": password},
                                format="json")


class LoginLogoutTests(AuthApiBase):
    def test_login_by_username_sets_session(self):
        resp = self.login("owner", "owner-pass-123")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["user"]["username"], "owner")
        # Session now holds the logged-in user.
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["username"], "owner")

    def test_login_is_case_insensitive_on_username(self):
        resp = self.login("OWNER", "owner-pass-123")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_login_by_email_is_not_supported(self):
        # Login is username-only (auto-created emails are @cedar.com and not
        # real addresses), so supplying an email must not authenticate.
        resp = self.login("owner@example.com", "owner-pass-123")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_wrong_password_fails(self):
        resp = self.login("owner", "wrong-password")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_user_fails(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        resp = self.login("owner", "owner-pass-123")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_clears_session(self):
        self.login("owner", "owner-pass-123")
        resp = self.client.post("/api/auth/logout/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, status.HTTP_401_UNAUTHORIZED)


class MeProfileTests(AuthApiBase):
    def test_unauthenticated_me_fails(self):
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_profile_valid(self):
        self.login("owner", "owner-pass-123")
        resp = self.client.patch("/api/auth/me/",
                                 {"phone": "5551234", "first_name": "Olivia"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["first_name"], "Olivia")
        self.assertEqual(resp.data["phone"], "5551234")

    def test_patch_profile_cannot_escalate_role(self):
        self.login("accountant", "acc-pass-123")
        resp = self.client.patch("/api/auth/me/", {"role": Role.OWNER}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.role, Role.ACCOUNTANT)


class ChangePasswordTests(AuthApiBase):
    def test_change_password(self):
        self.login("owner", "owner-pass-123")
        resp = self.client.post("/api/auth/change-password/",
                                {"old_password": "owner-pass-123",
                                 "new_password": "brand-new-pass-456"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password("brand-new-pass-456"))

    def test_change_password_wrong_current(self):
        self.login("owner", "owner-pass-123")
        resp = self.client.post("/api/auth/change-password/",
                                {"old_password": "nope", "new_password": "brand-new-pass-456"},
                                format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class PasswordResetTests(AuthApiBase):
    def test_request_reset_sends_email_with_link(self):
        resp = self.client.post("/api/auth/request-password-reset/",
                                {"email": "owner@example.com"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("owner@example.com", mail.outbox[0].to)
        self.assertIn("reset", mail.outbox[0].subject.lower())

    def test_request_reset_unknown_email_success_but_no_email(self):
        resp = self.client.post("/api/auth/request-password-reset/",
                                {"email": "nobody@example.com"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_complete_reset_with_valid_uid_and_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.owner.pk))
        token = default_token_generator.make_token(self.owner)
        resp = self.client.post("/api/auth/reset-password/",
                                {"uid": uid, "token": token,
                                 "new_password": "fresh-password-789"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password("fresh-password-789"))

    def test_complete_reset_with_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.owner.pk))
        resp = self.client.post("/api/auth/reset-password/",
                                {"uid": uid, "token": "bad-token",
                                 "new_password": "fresh-password-789"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password("owner-pass-123"))


class UserManagementRbacTests(AuthApiBase):
    def test_unauthenticated_cannot_list_users(self):
        resp = self.client.get("/api/auth/users/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_accountant_cannot_manage_users(self):
        self.login("accountant", "acc-pass-123")
        resp = self.client.get("/api/auth/users/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        create = self.client.post("/api/auth/users/",
                                  {"username": "hacker", "email": "h@example.com",
                                   "first_name": "H", "last_name": "K",
                                   "role": Role.ACCOUNTANT, "password": "password-123"},
                                  format="json")
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_register_user(self):
        self.login("owner", "owner-pass-123")
        resp = self.client.post("/api/auth/users/",
                                {"username": "newusr", "email": "new@example.com",
                                 "first_name": "New", "last_name": "User",
                                 "role": Role.ACCOUNTANT, "password": "password-123"},
                                format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["username"], "newusr")
        self.assertNotIn("password", resp.data)
        created = User.objects.get(username="newusr")
        self.assertTrue(created.check_password("password-123"))

    def test_owner_can_deactivate_and_activate(self):
        self.login("owner", "owner-pass-123")
        deact = self.client.post(f"/api/auth/users/{self.acc.pk}/deactivate/")
        self.assertEqual(deact.status_code, status.HTTP_200_OK)
        self.acc.refresh_from_db()
        self.assertFalse(self.acc.is_active)
        act = self.client.post(f"/api/auth/users/{self.acc.pk}/activate/")
        self.assertEqual(act.status_code, status.HTTP_200_OK)
        self.acc.refresh_from_db()
        self.assertTrue(self.acc.is_active)

    def test_create_auto_generates_username_email_and_password(self):
        self.login("owner", "owner-pass-123")
        resp = self.client.post("/api/auth/users/",
                                {"first_name": "First", "last_name": "User",
                                 "role": Role.ACCOUNTANT},
                                format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # username -> firstname-lastname; email -> firstname.lastname@cedar.com
        self.assertEqual(resp.data["username"], "first-user")
        self.assertEqual(resp.data["email"], "first.user@cedar.com")
        self.assertNotIn("password", resp.data)
        created = User.objects.get(username="first-user")
        # A password was generated and hashed (never plaintext).
        self.assertTrue(created.password_hash)
        self.assertFalse(created.check_password("first-user"))

    def test_create_emails_credentials(self):
        self.login("owner", "owner-pass-123")
        resp = self.client.post("/api/auth/users/",
                                {"first_name": "Mail", "last_name": "Recipient",
                                 "role": Role.OWNER},
                                format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["mail.recipient@cedar.com"])
        self.assertIn("Username:", mail.outbox[0].body)
        self.assertIn("Password:", mail.outbox[0].body)

    def test_create_with_explicit_username_email_password(self):
        self.login("owner", "owner-pass-123")
        resp = self.client.post("/api/auth/users/",
                                {"username": "explicit", "email": "explicit@example.com",
                                 "first_name": "Ex", "last_name": "Plicit",
                                 "role": Role.ACCOUNTANT, "password": "explicit-pass-123"},
                                format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["username"], "explicit")
        created = User.objects.get(username="explicit")
        self.assertTrue(created.check_password("explicit-pass-123"))
