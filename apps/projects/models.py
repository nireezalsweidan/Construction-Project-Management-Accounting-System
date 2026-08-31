import uuid

from django.db import models


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

    # TODO(team): once apps/employees and apps/clients exist, convert these
    # to real ForeignKeys — models.ForeignKey("employees.Employee", ...) and
    # models.ForeignKey("clients.Client", ...). The DB-level FK constraint
    # already exists in Postgres either way, so this is a Python-only change,
    # no migration required (managed=False).
    manager_id = models.UUIDField(null=True, blank=True)
    buyer_id = models.UUIDField(null=True, blank=True)

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