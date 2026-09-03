"""
Models for the ``contractors`` app -- Contractor Management API.

All three models are ``managed = False``: they map existing Supabase tables
(``contractors``, ``project_contractors``, ``documents``) that this app does
not own the lifecycle of. The SQL in ``database/construction_management_supabase.sql``
is the source of truth for column names, types, nullability, defaults, and
enum values -- nothing here creates, alters, or migrates those tables.

Contractors are pure business records: they get no login, password, role,
or permissions. Access is restricted to authenticated system users via the
existing DRF ``IsAuthenticated`` + session-authentication setup used by the
Supplier/Client APIs.
"""
import uuid

from django.db import models

from projects.models import Project


class Contractor(models.Model):
    """Business record for a contractor/sub-contractor."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        TERMINATED = "TERMINATED", "Terminated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    # schema stores phone as TEXT (unlike clients/suppliers VARCHAR(50))
    phone = models.TextField(blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    contract_details = models.TextField(blank=True, null=True)
    specialization = models.CharField(max_length=255, blank=True, null=True)
    payment_terms = models.CharField(max_length=255, blank=True, null=True)
    rate = models.DecimalField(max_digits=18, decimal_places=2, blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "contractors"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ContractorProjectAssignment(models.Model):
    """
    Maps ``project_contractors`` -- a many-to-many assignment between a
    contractor and a project, carrying contract amount, assignment/release
    dates, and assignment status.

    The schema has no UNIQUE(project_id, contractor_id) constraint, so
    duplicate assignments are prevented at the serializer level (see
    ``serializers.ContractorAssignSerializer``).
    """

    class Status(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        RELEASED = "RELEASED", "Released"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Schema: project_id REFERENCES projects(id) ON DELETE CASCADE.
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        db_column="project_id",
        related_name="contractor_assignments",
    )
    # Schema: contractor_id REFERENCES contractors(id) with no ON DELETE --
    # a contractor with assignments cannot be deleted outright.
    contractor = models.ForeignKey(
        Contractor,
        on_delete=models.PROTECT,
        db_column="contractor_id",
        related_name="project_assignments",
    )
    contract_amount = models.DecimalField(
        max_digits=18, decimal_places=2, blank=True, null=True
    )
    assigned_at = models.DateField()
    released_at = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ASSIGNED
    )

    class Meta:
        managed = False
        db_table = "project_contractors"
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.contractor_id} on {self.project_id}"


class ContractorDocument(models.Model):
    """
    Read-only mapping onto the shared ``documents`` table, filtered to
    ``entity_type='contractor'``. The real owner is the Document Management
    module; this just lets the Contractor API list documents linked to a
    given contractor. Same pattern as ``projects.ProjectDocument``.
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
        # managed=False deliberately -- the shared documents table is owned
        # by Document Management; a second managed model on the same
        # db_table would trip models.E028.

    def __str__(self):
        return self.file_name