"""
Test-only utility for the ``users`` app.

``User.Meta.managed = False`` (see models.py) means Django's normal
migration/test-database setup never creates the ``users`` table -- it
assumes the table already exists elsewhere, which is true against the
live Supabase DB but not against a fresh, empty test database. Any test
that needs to create a ``User`` row (directly, or indirectly via a FK
like ``purchasing.PurchaseOrder.created_by``) needs the table to exist
for the duration of that test class.

``WithUsersTableMixin`` creates the table via the schema editor before
Django's ``TestCase`` wraps the class in its own transaction (so the
CREATE TABLE is a plain, separately-committed statement, not something
that would be rolled back by the test transaction machinery), and drops
it again after that wrapping closes.
"""
from django.db import connection

from .models import User


class WithUsersTableMixin:
    """
    Mix into any Django TestCase subclass that needs to create User rows.

    Usage: ``class MyTests(WithUsersTableMixin, TestCase): ...`` --
    WithUsersTableMixin must come first in the MRO so its setUpClass/
    tearDownClass wrap (not get wrapped by) TestCase's own.
    """

    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            editor.create_model(User)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            editor.delete_model(User)
