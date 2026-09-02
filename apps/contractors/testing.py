"""
Test-only utility for the ``contractors`` app.

All ``contractors`` models are ``managed = False`` (they reflect existing
Supabase tables owned elsewhere -- see models.py), so Django's normal
test-database setup never creates ``contractors``, ``project_contractors``,
or ``documents``. Any test that needs to persist real rows must create those
tables for the duration of the test class -- the same pattern as
``users.testing.WithUsersTableMixin`` and
``projects.testing.WithProjectsTableMixin``.

Tests that also create Project rows should mix ``WithProjectsTableMixin`` in
BEFORE this mixin so the ``projects`` table (referenced by
``ContractorProjectAssignment.project``) exists first.
"""
from django.db import connection

from .models import Contractor, ContractorDocument, ContractorProjectAssignment


class WithContractorsTableMixin:
    """
    Mix into any Django TestCase subclass that needs to persist real
    Contractor / ContractorProjectAssignment / ContractorDocument rows.

    Usage: ``class MyTests(WithContractorsTableMixin, TestCase): ...`` --
    must come first in the MRO so its setUpClass/tearDownClass wrap (not
    get wrapped by) TestCase's own.
    """

    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            editor.create_model(Contractor)
            editor.create_model(ContractorProjectAssignment)
            editor.create_model(ContractorDocument)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            editor.delete_model(ContractorDocument)
            editor.delete_model(ContractorProjectAssignment)
            editor.delete_model(Contractor)