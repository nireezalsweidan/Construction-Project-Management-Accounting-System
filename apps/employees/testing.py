"""
Test-only utility for the ``employees`` app.

All ``employees`` models are ``managed = False`` (they reflect existing
Supabase tables owned elsewhere -- see models.py), so Django's normal
test-database setup never creates ``employees`` or ``project_employees``.
Any test that needs to persist real rows must create those tables for the
duration of the test class -- the same pattern as
``users.testing.WithUsersTableMixin`` and
``projects.testing.WithProjectsTableMixin``.

Tests that also create Project rows should mix ``WithProjectsTableMixin``
(and ``WithClientsTableMixin``, since Project references ``clients`` via
``buyer_id``) in BEFORE this mixin so the ``projects`` / ``clients`` tables
(referenced by the assignment) exist first.
"""
from django.db import connection

from .models import Employee, EmployeeProjectAssignment


class WithEmployeesTableMixin:
    """
    Mix into any Django TestCase subclass that needs to persist real
    Employee / EmployeeProjectAssignment rows.

    Usage: ``class MyTests(WithEmployeesTableMixin, TestCase): ...`` --
    must come first in the MRO so its setUpClass/tearDownClass wrap (not
    get wrapped by) TestCase's own.
    """

    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            editor.create_model(Employee)
            editor.create_model(EmployeeProjectAssignment)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            editor.delete_model(EmployeeProjectAssignment)
            editor.delete_model(Employee)
