"""
Test-only utility for the ``clients`` app.

``Client.Meta.managed = False`` (it reflects the existing ``clients``
table, owned elsewhere -- see models.py) means Django's normal test-
database setup never creates that table. Any test that needs to persist
a real ``Client`` row (directly, or indirectly via a nullable FK like
``accounting.FinancialTransaction.client``, even when left unset --
SQLite validates an FK column's target table exists at INSERT time
regardless of the value being NULL) needs the table to exist for the
duration of that test class.

Same pattern as ``users.testing.WithUsersTableMixin`` (CPMAS-29) and
``projects.testing.WithProjectsTableMixin`` (CPMAS-33).
"""
from django.db import connection

from .models import Client


class WithClientsTableMixin:
    """
    Mix into any Django TestCase subclass that needs to persist real
    Client rows (or merely reference the clients table via a nullable
    FK). Must come first in the MRO so its setUpClass/tearDownClass wrap
    (not get wrapped by) TestCase's own.
    """

    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            editor.create_model(Client)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            editor.delete_model(Client)
