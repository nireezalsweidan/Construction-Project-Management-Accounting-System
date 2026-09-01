import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from clients.models import Client


class Project(models.Model):
    """
    Maps onto the existing `projects` table in Supabase (see
    construction_management_supabase.sql). managed=False — this table
    was created by the shared SQL script, Django must not try to
    create/alter/drop it.
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
    # FK constraint already exists in Postgres either way, so this is a
    # Python-only change, no migration required (managed=False).
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
        managed = False
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
        managed = False
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

    def __str__(self):
        return self.file_name


class Phase(models.Model):
    """
    Project Planning — maps onto the existing `project_phases` table.
    managed=False — created by construction_management_supabase.sql.

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
        managed = False
        db_table = "project_phases"
        ordering = ["project_id", "sequence_number"]

    def __str__(self):
        return f"{self.project_id} · {self.sequence_number}. {self.name}"