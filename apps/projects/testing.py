"""
Test-only utility for the ``projects`` app.

``Project.Meta.managed = False`` (it reflects the existing ``projects``
table, owned elsewhere -- see models.py) means Django's normal test-
database setup never creates that table. Any test that needs to persist
a real ``Project`` row (directly, or indirectly via a FK like
``expenses.Expense.project``) needs the table to exist for the duration
of that test class.

Same pattern as ``users.testing.WithUsersTableMixin`` (CPMAS-29): create
the table via the schema editor before Django's ``TestCase`` wraps the
class in its own transaction, drop it again after.
"""
from django.db import connection

from .models import Project


class WithProjectsTableMixin:
    """
    Mix into any Django TestCase subclass that needs to persist real
    Project rows.

    Usage: ``class MyTests(WithProjectsTableMixin, TestCase): ...`` --
    must come first in the MRO so its setUpClass/tearDownClass wrap
    (not get wrapped by) TestCase's own.
    """

    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            editor.create_model(Project)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            editor.delete_model(Project)
