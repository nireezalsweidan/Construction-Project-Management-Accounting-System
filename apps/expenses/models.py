"""
Models for the ``expenses`` app -- Expense Management slice (CPMAS-33).

Implements ``ExpenseCategory`` and ``Expense``, matching the
``expense_categories`` / ``expenses`` tables in the approved schema
(BRD 5.20 Expense Management).

Unlike purchase orders and supplier invoices, expenses have no line-item
breakdown -- ``amount``/``tax_amount`` are direct fields on the row
itself, not derived from a child table. So there's no
``services.compute_item_amounts``-style logic here; the only business
rule enforced outside the serializer/model is the status workflow (see
``expenses.services.transition_status``).

``Expense.status`` matches the live Postgres enum ``expense_status_enum``
(PENDING, APPROVED, PAID, REJECTED) exactly.

Two FKs are intentionally NOT modeled, following the same
deferred-dependency precedent used throughout this codebase:
- ``ExpenseCategory.account`` -- optional FK into ``accounts.Account``;
  the Accounting app (CPMAS-34) doesn't exist yet.
- ``Expense.employee``/``Expense.contractor`` -- optional FKs into
  ``employees.Employee``/``contractors.Contractor``, neither built yet.
Each is a straightforward additive migration once its target app lands.
"""
import uuid

from django.db import models


class ExpenseCategory(models.Model):
    """
    A category expenses are classified under (e.g. Materials, Labor,
    Transportation, Utilities).

    Matches the ``expense_categories`` table in the approved schema.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'expense_categories'
        ordering = ['name']
        verbose_name = 'Expense Category'
        verbose_name_plural = 'Expense Categories'

    def __str__(self):
        return self.name


class Expense(models.Model):
    """
    A project-related expense (materials, labor, contractor, or other
    cost) contributing to that project's actual cost (BR 12.2).

    Matches the ``expenses`` table. ``status`` is only ever changed
    through ``expenses.services.transition_status`` (called from the
    approve/mark_paid/reject API actions) -- see that module's docstring
    for why a raw status PATCH isn't exposed.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        PAID = 'PAID', 'Paid'
        REJECTED = 'REJECTED', 'Rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT: an expense is a financial record tied to a specific
    # project's actual cost -- it shouldn't be able to end up pointing
    # at nothing if the project is deleted. Matches the live DB's plain
    # REFERENCES with no ON DELETE clause (defaults to NO ACTION, i.e.
    # blocks the delete).
    project = models.ForeignKey('projects.Project', on_delete=models.PROTECT, related_name='expenses')

    # PROTECT: same reasoning -- an expense without a category would be
    # unclassified financial data, not a state to fall into silently.
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')

    # SET_NULL: losing a supplier reference shouldn't delete/block an
    # already-recorded expense -- same reasoning as Material.tax_rate
    # elsewhere in this codebase.
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.SET_NULL, blank=True, null=True, related_name='expenses')

    expense_date = models.DateField()
    description = models.TextField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=50, blank=True, null=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    notes = models.TextField(blank=True, null=True)

    # SET_NULL: who created an expense record is audit context, not a
    # hard requirement -- losing the user shouldn't delete the expense
    # itself. db_column='created_by': unlike most FKs in this schema
    # (project_id, category_id, ...), the live column has no _id suffix
    # -- same naming quirk as PurchaseOrder.created_by (CPMAS-30).
    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='expenses_created', db_column='created_by',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'expenses'
        ordering = ['-expense_date', '-created_at']
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'

    def __str__(self):
        return f"{self.description} ({self.amount}) on {self.expense_date}"
