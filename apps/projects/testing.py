"""
Test-only utility for the ``projects`` app.

``Project`` is now a real (``managed=True``) Django-owned table -- see
migration 0001's docstring for why it wasn't always: it briefly went
through a managed=False "reflection" phase, which is what this mixin was
originally written against. Since CPMAS-25's migration cleanup, the
project's own migrations already create the ``projects`` table once, up
front, when the whole test database is built -- before any test class's
setUpClass runs. This mixin now just needs to not collide with that: it
checks whether the table already exists and, if so, leaves creating/
dropping it alone entirely (some other test class getting there first,
or the migrations themselves, already did the real work).

Kept (rather than deleted) so every existing ``WithProjectsTableMixin``
usage across the other apps' test suites keeps working unchanged -- this
mixin's contract ("the projects table exists for the duration of this
test class") is still honoured, just by a cheaper path when the table
was already created by migrations.
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

    _created_projects_table = False

    @classmethod
    def setUpClass(cls):
        if Project._meta.db_table not in connection.introspection.table_names():
            with connection.schema_editor() as editor:
                editor.create_model(Project)
            cls._created_projects_table = True
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if cls._created_projects_table:
            with connection.schema_editor() as editor:
                editor.delete_model(Project)
