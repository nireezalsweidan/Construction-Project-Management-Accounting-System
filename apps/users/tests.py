"""
Tests for the ``users`` app (minimal, managed=False reflection of the
live ``users`` table -- see models.py).

Also exercises WithUsersTableMixin itself (testing.py): every other
app's tests that need a User row depend on this mixin creating the
table correctly, so it's worth a direct test of its own.
"""
from django.test import TestCase

from .models import User
from .testing import WithUsersTableMixin


class UserModelTests(WithUsersTableMixin, TestCase):
    def test_create_and_retrieve(self):
        user = User.objects.create(
            username="owner1", email="owner1@example.com", password_hash="x",
            first_name="Jane", last_name="Doe", role="owner",
        )
        self.assertEqual(str(user), "owner1")
        self.assertTrue(user.is_active)  # default=True

        fetched = User.objects.get(pk=user.pk)
        self.assertEqual(fetched.email, "owner1@example.com")

    def test_username_and_email_are_unique(self):
        User.objects.create(
            username="dup", email="a@example.com", password_hash="x",
            first_name="A", last_name="B", role="owner",
        )
        with self.assertRaises(Exception):
            User.objects.create(
                username="dup", email="b@example.com", password_hash="x",
                first_name="C", last_name="D", role="owner",
            )
