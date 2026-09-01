"""
Tests for the ``expenses`` app -- Expense Management slice (CPMAS-33).

Organized into:
- Model tests: constraints and validation (positive amount, non-negative
  tax_amount).
- Service tests: transition_status (the status workflow).
- API tests: the same behaviors through the real DRF endpoints --
  status-change actions, read-only status enforcement, and filtering.
"""
from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from projects.models import Project
from projects.testing import WithProjectsTableMixin
from suppliers.models import Supplier
from users.testing import WithUsersTableMixin

from .models import Expense, ExpenseCategory
from .services import transition_status


class ExpensesTestBase(WithProjectsTableMixin, WithUsersTableMixin, TestCase):
    """
    Expense.created_by FKs to users.User (managed=False, see
    users.testing) even though no test here sets it explicitly --
    SQLite validates an FK column's target table exists at INSERT time
    regardless of whether the value being inserted is NULL, so that
    table has to exist too, not just projects.
    """

    """Shared fixtures: a project (real, from CPMAS-47) and an expense category."""

    def setUp(self):
        self.project = Project.objects.create(
            name="DUMMY Test Project", code="DUMMY-PROJ-1", project_type=Project.TYPE_WHOLE_BUILDING,
            start_date="2026-01-01", contract_value=Decimal("500000.00"),
        )
        self.category = ExpenseCategory.objects.create(name="Materials")

    def make_expense(self, **kwargs):
        defaults = dict(
            project=self.project, category=self.category, expense_date="2026-08-31",
            description="Cement delivery", amount=Decimal("250.00"),
        )
        defaults.update(kwargs)
        return Expense.objects.create(**defaults)


class ExpenseModelTests(ExpensesTestBase):
    def test_create_with_required_fields(self):
        expense = self.make_expense()
        self.assertEqual(expense.status, Expense.Status.PENDING)
        self.assertEqual(expense.tax_amount, Decimal("0.00"))

    def test_category_name_must_be_unique(self):
        with self.assertRaises(Exception):
            ExpenseCategory.objects.create(name="Materials")

    def test_supplier_deletion_sets_expense_supplier_to_null(self):
        supplier = Supplier.objects.create(name="ACME")
        expense = self.make_expense(supplier=supplier)
        supplier.delete()
        expense.refresh_from_db()
        self.assertIsNone(expense.supplier)


class TransitionStatusTests(ExpensesTestBase):
    def test_pending_to_approved_to_paid(self):
        expense = self.make_expense()
        transition_status(expense, Expense.Status.APPROVED)
        self.assertEqual(expense.status, Expense.Status.APPROVED)
        transition_status(expense, Expense.Status.PAID)
        self.assertEqual(expense.status, Expense.Status.PAID)

    def test_cannot_skip_to_paid(self):
        expense = self.make_expense()
        with self.assertRaises(ValidationError):
            transition_status(expense, Expense.Status.PAID)

    def test_can_reject_from_approved(self):
        expense = self.make_expense()
        transition_status(expense, Expense.Status.APPROVED)
        transition_status(expense, Expense.Status.REJECTED)
        self.assertEqual(expense.status, Expense.Status.REJECTED)

    def test_cannot_leave_rejected(self):
        expense = self.make_expense()
        transition_status(expense, Expense.Status.REJECTED)
        with self.assertRaises(ValidationError):
            transition_status(expense, Expense.Status.PENDING)


class ExpenseAPITests(ExpensesTestBase):
    def setUp(self):
        super().setUp()
        django_user = DjangoUser.objects.create_user(username="apitester", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(user=django_user)

    def test_create_expense_via_api(self):
        response = self.client.post("/api/expenses/expenses/", {
            "project": str(self.project.id), "category": str(self.category.id),
            "expense_date": "2026-08-31", "description": "Steel delivery", "amount": "1000.00",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "PENDING")

    def test_negative_amount_rejected(self):
        response = self.client.post("/api/expenses/expenses/", {
            "project": str(self.project.id), "category": str(self.category.id),
            "expense_date": "2026-08-31", "description": "Bad", "amount": "-5.00",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_status_cannot_be_set_directly_via_patch(self):
        expense = self.make_expense()
        response = self.client.patch(f"/api/expenses/expenses/{expense.id}/", {"status": "PAID"}, format="json")
        self.assertEqual(response.json()["status"], "PENDING")

    def test_approve_mark_paid_workflow(self):
        expense = self.make_expense()
        approve = self.client.post(f"/api/expenses/expenses/{expense.id}/approve/")
        self.assertEqual(approve.json()["status"], "APPROVED")
        paid = self.client.post(f"/api/expenses/expenses/{expense.id}/mark_paid/")
        self.assertEqual(paid.json()["status"], "PAID")

    def test_invalid_transition_via_api_returns_400(self):
        expense = self.make_expense()
        response = self.client.post(f"/api/expenses/expenses/{expense.id}/mark_paid/")
        self.assertEqual(response.status_code, 400)

    def test_filter_by_project(self):
        other_project = Project.objects.create(
            name="Other Project", code="DUMMY-PROJ-2", project_type=Project.TYPE_WHOLE_BUILDING,
            start_date="2026-01-01", contract_value=Decimal("100000.00"),
        )
        self.make_expense()
        self.make_expense(project=other_project, description="Other project's expense")

        response = self.client.get(f"/api/expenses/expenses/?project={self.project.id}")
        self.assertEqual(response.json()["count"], 1)

    def test_filter_by_status(self):
        expense = self.make_expense()
        self.client.post(f"/api/expenses/expenses/{expense.id}/approve/")
        self.make_expense(description="Still pending")

        response = self.client.get("/api/expenses/expenses/?status=approved")
        self.assertEqual(response.json()["count"], 1)

    def test_anonymous_request_is_rejected(self):
        anon = APIClient()
        response = anon.get("/api/expenses/expenses/")
        self.assertEqual(response.status_code, 403)
