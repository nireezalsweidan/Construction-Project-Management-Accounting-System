"""
Models for the ``employees`` app -- Employee Management API.

Both models are ``managed = False``: they map existing Supabase tables
(``employees``, ``project_employees``) that this app does not own the
lifecycle of. The SQL in ``database/construction_management_supabase.sql``
is the source of truth for column names, types, nullability, defaults, and
enum values -- nothing here creates, alters, or migrates those tables.

Employees are pure business records: they get no login, password, role, or
permissions. Access is restricted to authenticated system users via the
existing DRF ``IsAuthenticated`` + session-authentication setup used by the
Supplier/Client/Contractor APIs.
"""
import uuid

from django.db import models

from projects.models import Project


class Employee(models.Model):
    """Business record for an employee of the company."""

    class EmploymentStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ON_LEAVE = "ON_LEAVE", "On Leave"
        TERMINATED = "TERMINATED", "Terminated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee_number = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    position = models.CharField(max_length=150, blank=True, null=True)
    department = models.CharField(max_length=150, blank=True, null=True)
    employment_status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE,
    )
    labor_rate = models.DecimalField(max_digits=18, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "employees"
        ordering = ["name"]

    def __str__(self):
        return self.name


class EmployeeProjectAssignment(models.Model):
    """
    Maps ``project_employees`` -- a many-to-many assignment between an
    employee and a project, carrying assignment/release dates and an
    optional role.

    Unlike ``project_contractors`` the schema puts a real
    ``UNIQUE(project_id, employee_id)`` constraint on this table, and there
    is no assignment-status column -- an assignment is "active" while
    ``released_at`` is null. Duplicate assignment is therefore enforced by
    the database itself (reflected here via ``unique_together``).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Schema: project_id REFERENCES projects(id) ON DELETE CASCADE.
    # (related_name differs from projects.ProjectEmployee's to avoid an
    # E304 reverse-accessor clash -- two models map the project_employees
    # table, but reverse accessors from Project must be unique.)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        db_column="project_id",
        related_name="employee_project_assignments",
    )
    # Schema: employee_id REFERENCES employees(id) with no ON DELETE --
    # an employee with assignments cannot be deleted outright.
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        db_column="employee_id",
        related_name="project_assignments",
    )
    assigned_at = models.DateField()
    released_at = models.DateField(blank=True, null=True)
    role_on_project = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "project_employees"
        unique_together = (("project", "employee"),)
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.employee_id} on {self.project_id}"
