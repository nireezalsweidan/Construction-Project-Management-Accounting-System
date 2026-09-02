import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from clients.models import Client

# Real Expense Management app (Mohammad, CPMAS-33) — was a temporary
# read-only mirror in this file before that app existed; now imports the
# real thing. Requires the `expenses` app to be present in this branch
# (merge/rebase `dev` in if you see an ImportError here).
from expenses.models import Expense


class Project(models.Model):
    """
    Maps onto the existing `projects` table in Supabase (see
    construction_management_supabase.sql). Django owns this table's
    migrations going forward (see Meta.db_table + apps/README notes on
    adopting an existing table via `migrate --fake-initial`).
    """

    STATUS_PLANNING = "PLANNING"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_ON_HOLD = "ON_HOLD"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_PLANNING, "Planning"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_ON_HOLD, "On Hold"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    # Allowed forward transitions for the status workflow. Enforced in
    # ProjectSerializer.validate_status — Postgres just stores the enum
    # value, it doesn't know about the workflow rules.
    ALLOWED_TRANSITIONS = {
        STATUS_PLANNING: {STATUS_ACTIVE, STATUS_CANCELLED},
        STATUS_ACTIVE: {STATUS_ON_HOLD, STATUS_COMPLETED, STATUS_CANCELLED},
        STATUS_ON_HOLD: {STATUS_ACTIVE, STATUS_CANCELLED},
        STATUS_COMPLETED: set(),   # final
        STATUS_CANCELLED: set(),  # final
    }

    TYPE_WHOLE_BUILDING = "WHOLE_BUILDING"
    TYPE_MULTI_UNIT = "MULTI_UNIT"
    TYPE_CHOICES = [
        (TYPE_WHOLE_BUILDING, "Whole Building"),
        (TYPE_MULTI_UNIT, "Multi Unit"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # TODO(team): once the employees app exists, convert this to a real
    # ForeignKey — models.ForeignKey("employees.Employee", ...). The DB-level
    # FK constraint already exists in Postgres either way; this is a
    # Python-only model change, but since it's now managed=True, remember
    # to run makemigrations/migrate --fake-initial is NOT needed again here
    # (that's only for the initial adoption) — a normal migration is fine
    # for this specific change, since it's just adding a Django-level FK on
    # top of a UUID column that's already there and already FK-constrained
    # at the DB level; Django's ALTER for that is a no-op/safe.
    manager_id = models.UUIDField(null=True, blank=True)

    # Upgraded from a plain UUIDField now that the clients app exists.
    # db_column matches Django's own default attname for a FK named "buyer"
    # anyway, but it's kept explicit since the physical column predates this
    # model. Note: `project.buyer_id` still works as a plain UUID read
    # (Django auto-generates that attname for any FK), so existing filters
    # like Project.objects.filter(buyer_id=client.id) elsewhere didn't need
    # to change — only this field's own type did.
    buyer = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        db_column="buyer_id",
        null=True,
        blank=True,
        related_name="projects",
    )

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True)
    location = models.TextField(blank=True, null=True)
    project_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    estimated_sale_price = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    actual_sale_price = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )

    start_date = models.DateField()
    expected_completion_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)

    contract_value = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNING
    )
    description = models.TextField(blank=True, null=True)
    is_archived = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "projects"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class ProjectEmployee(models.Model):
    """
    Maps onto `project_employees` — employee assignment to a project.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        db_column="project_id",
        related_name="employee_assignments",
    )
    # TODO(team): FK to employees.Employee once that app exists.
    employee_id = models.UUIDField()
    assigned_at = models.DateField()
    released_at = models.DateField(null=True, blank=True)
    role_on_project = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        db_table = "project_employees"
        unique_together = (("project", "employee_id"),)

    def __str__(self):
        return f"employee {self.employee_id} on project {self.project_id}"


class ProjectDocument(models.Model):
    """
    Read-mostly mapping onto the shared `documents` table, filtered to
    entity_type='project'. Full upload/delete/tagging CRUD belongs to the
    Document Management module (Nada) — this just lets the Projects API
    list documents linked to a given project.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.UUIDField()
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_type = models.CharField(max_length=100, null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    document_type = models.CharField(max_length=100, null=True, blank=True)
    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "documents"
        # Read-only mirror into a table this app doesn't own — kept
        # managed=False deliberately. The real owner is Document
        # Management (Nada's task); if this were managed=True too,
        # Django would refuse to run (models.E028: two managed models
        # can't claim the same db_table) the moment that app exists.

    def __str__(self):
        return self.file_name


class Phase(models.Model):
    """
    Project Planning — maps onto the existing `project_phases` table.

    Lives in this app (not a separate `planning` app) since the team's
    apps/ folder doesn't have one — phases are just as much "project core"
    as the Project model itself.
    """

    STATUS_NOT_STARTED = "NOT_STARTED"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_ON_HOLD = "ON_HOLD"
    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, "Not Started"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_ON_HOLD, "On Hold"),
    ]

    # Allowed forward transitions — enforced in PhaseSerializer.validate_status,
    # same approach as Project.ALLOWED_TRANSITIONS above.
    ALLOWED_TRANSITIONS = {
        STATUS_NOT_STARTED: {STATUS_IN_PROGRESS},
        STATUS_IN_PROGRESS: {STATUS_ON_HOLD, STATUS_COMPLETED},
        STATUS_ON_HOLD: {STATUS_IN_PROGRESS},
        STATUS_COMPLETED: set(),  # final
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        db_column="project_id",
        related_name="phases",
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # TODO(team): FK to employees.Employee once that app exists (Mahmoud's
    # task). DB-level FK constraint already exists in Postgres either way.
    responsible_emp_id = models.UUIDField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_NOT_STARTED
    )
    progress_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    sequence_number = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_phases"
        ordering = ["project_id", "sequence_number"]

    def __str__(self):
        return f"{self.project_id} · {self.sequence_number}. {self.name}"


# ---------------------------------------------------------------------------
# Project Budgeting
# ---------------------------------------------------------------------------

class Budget(models.Model):
    """
    Maps onto the existing `project_budgets` table. A project can have
    multiple budgets over time (e.g. an original + a revised version) —
    see get_active_budget() below for how "the current budget" is picked.
    """

    STATUS_DRAFT = "DRAFT"
    STATUS_APPROVED = "APPROVED"
    STATUS_REVISED = "REVISED"
    STATUS_CLOSED = "CLOSED"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REVISED, "Revised"),
        (STATUS_CLOSED, "Closed"),
    ]

    ALLOWED_TRANSITIONS = {
        STATUS_DRAFT: {STATUS_APPROVED},
        STATUS_APPROVED: {STATUS_REVISED, STATUS_CLOSED},
        STATUS_REVISED: {STATUS_APPROVED, STATUS_CLOSED},
        STATUS_CLOSED: set(),  # final
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, db_column="project_id", related_name="budgets"
    )
    name = models.CharField(max_length=255)
    total_budget = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_budgets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.project_id})"


class BudgetItem(models.Model):
    """
    Maps onto the existing `budget_items` table. `category` is a free-text
    VARCHAR(50) at the DB level — constrained here to the five fixed
    categories the task asks for. Optionally scoped to a Phase.
    """

    CATEGORY_MATERIALS = "MATERIALS"
    CATEGORY_LABOR = "LABOR"
    CATEGORY_CONTRACTORS = "CONTRACTORS"
    CATEGORY_EQUIPMENT = "EQUIPMENT"
    CATEGORY_OTHER = "OTHER"
    CATEGORY_CHOICES = [
        (CATEGORY_MATERIALS, "Materials"),
        (CATEGORY_LABOR, "Labor"),
        (CATEGORY_CONTRACTORS, "Contractors"),
        (CATEGORY_EQUIPMENT, "Equipment"),
        (CATEGORY_OTHER, "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    budget = models.ForeignKey(
        Budget, on_delete=models.CASCADE, db_column="budget_id", related_name="items"
    )
    phase = models.ForeignKey(
        Phase,
        on_delete=models.SET_NULL,
        db_column="phase_id",
        null=True,
        blank=True,
        related_name="budget_items",
    )
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True, null=True)
    budgeted_amount = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        db_table = "budget_items"

    def __str__(self):
        return f"{self.category} — {self.budgeted_amount}"



def normalize_category_name(name):
    """'Materials' / 'materials ' / 'MATERIALS' -> 'MATERIALS', so an
    expense_categories row matches a BudgetItem.CATEGORY_* value regardless
    of how it was capitalized when seeded."""
    return (name or "").strip().upper().replace(" ", "_")


def get_active_budget(project_id):
    """
    "The" budget for a project, when the API needs a single answer (e.g.
    the project detail page) rather than the full version history:
    prefer the most recent APPROVED/REVISED budget; fall back to the
    most recent DRAFT if nothing's been approved yet.
    """
    qs = Budget.objects.filter(project_id=project_id)
    active = qs.filter(status__in=[Budget.STATUS_APPROVED, Budget.STATUS_REVISED]).first()
    return active or qs.first()


def get_budget_summary(budget):
    """
    Budget vs Actual, grouped by the five fixed categories.
    variance = actual - budgeted (positive = over budget).
    remaining = budgeted - actual (negative = over budget).
    """
    from decimal import Decimal

    from django.db.models import F, Sum

    items = BudgetItem.objects.filter(budget=budget)
    budgeted_by_category = {
        row["category"]: row["total"]
        for row in items.values("category").annotate(total=Sum("budgeted_amount"))
    }

    actual_rows = (
        Expense.objects.filter(
            project_id=budget.project_id,
            # Only APPROVED/PAID count as real actual spend — PENDING isn't
            # confirmed yet, REJECTED never happened. (Expense.status is
            # only ever changed via expenses.services.transition_status,
            # per that app's own docstring — we just read the result here.)
            status__in=[Expense.Status.APPROVED, Expense.Status.PAID],
        )
        .values("category__name")
        .annotate(total=Sum(F("amount") + F("tax_amount")))
    )
    actual_by_category = {}
    for row in actual_rows:
        key = normalize_category_name(row["category__name"])
        actual_by_category[key] = actual_by_category.get(key, Decimal("0.00")) + (
            row["total"] or Decimal("0.00")
        )

    categories = []
    all_keys = set(budgeted_by_category) | set(actual_by_category)
    # Always show all five categories, even at zero, so the UI has a
    # consistent shape regardless of what's been itemized/spent so far.
    all_keys |= {c[0] for c in BudgetItem.CATEGORY_CHOICES}

    category_labels = dict(BudgetItem.CATEGORY_CHOICES)
    total_budgeted = Decimal("0.00")
    total_actual = Decimal("0.00")

    for key in sorted(all_keys):
        budgeted = budgeted_by_category.get(key, Decimal("0.00"))
        actual = actual_by_category.get(key, Decimal("0.00"))
        variance = actual - budgeted
        remaining = budgeted - actual
        total_budgeted += budgeted
        total_actual += actual
        categories.append(
            {
                "category": key,
                "category_display": category_labels.get(key, key.title()),
                "budgeted": budgeted,
                "actual": actual,
                "variance": variance,
                "remaining": remaining,
                "percent_used": float(actual / budgeted * 100) if budgeted else None,
            }
        )

    return {
        "budget_id": str(budget.id),
        "project_id": str(budget.project_id),
        "budget_name": budget.name,
        "budget_status": budget.status,
        "total_budget_header": budget.total_budget,
        "unallocated_budget": budget.total_budget - total_budgeted,
        "categories": categories,
        "totals": {
            "budgeted": total_budgeted,
            "actual": total_actual,
            "variance": total_actual - total_budgeted,
            "remaining": total_budgeted - total_actual,
        },
    }