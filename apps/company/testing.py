"""
Test-only utility for the ``company`` app.

``CompanyProfile.Meta.managed = False`` (it reflects the existing
``company_details`` table, owned elsewhere -- see models.py) means Django's
normal test-database setup never creates that table. Any test that needs to
persist a real ``CompanyProfile`` row, or merely view the Company settings
page (which reads the table on render), must create it for the duration of
that test class.

Same pattern as ``clients.testing.WithClientsTableMixin`` /
``users.testing.WithUsersTableMixin`` / ``projects.testing.WithProjectsTableMixin``.
"""
from django.db import connection

from .models import CompanyProfile


class WithCompanyDetailsTableMixin:
    """
    Mix into any Django TestCase subclass that needs the company_details
    table to exist. Must come first in the MRO so its setUpClass/tearDownClass
    wrap (not get wrapped by) TestCase's own.
    """

    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            editor.create_model(CompanyProfile)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            editor.delete_model(CompanyProfile)