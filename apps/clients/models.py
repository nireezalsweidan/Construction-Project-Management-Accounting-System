import uuid
from decimal import Decimal

from django.db import models
from django.db.models import Sum


class Client(models.Model):
    """
    Maps onto the existing `clients` table.

    NOTE: the task spec mentions a per-client "currency" field, but the
    actual `clients` table (construction_management_supabase.sql) has no
    currency column — only company_details.currency exists, at the company
    level. Not modeled here. See SETUP.md for the optional ALTER TABLE if
    the team decides they want per-client currency after all.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    tax_id = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "clients"
        ordering = ["name"]

    def __str__(self):
        return self.company_name or self.name


class ClientInvoiceSummary(models.Model):
    """
    Read-mostly mapping onto `client_invoices`, scoped to what's needed to
    list a client's invoices and compute their outstanding balance. Full
    invoice line items / create / send / void logic belongs to the Client
    Invoices module (Mahmoud) — not duplicated here.
    """

    STATUS_DRAFT = "DRAFT"
    STATUS_SENT = "SENT"
    STATUS_PARTIALLY_PAID = "PARTIALLY_PAID"
    STATUS_PAID = "PAID"
    STATUS_OVERDUE = "OVERDUE"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT, "Sent"),
        (STATUS_PARTIALLY_PAID, "Partially Paid"),
        (STATUS_PAID, "Paid"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.UUIDField()
    project_id = models.UUIDField(null=True, blank=True)
    unit_id = models.UUIDField(null=True, blank=True)
    invoice_number = models.CharField(max_length=100, unique=True)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "client_invoices"

    def __str__(self):
        return self.invoice_number


class ClientPayment(models.Model):
    """
    Read-mostly mapping onto `payments`, scoped to rows where client_id is
    set (i.e. incoming client payments). Payment recording/allocation logic
    belongs to the Payments module (Mahmoud).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_number = models.CharField(max_length=100, unique=True)
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    direction = models.CharField(max_length=20)
    payment_method = models.CharField(max_length=50)
    client_id = models.UUIDField(null=True, blank=True)
    supplier_id = models.UUIDField(null=True, blank=True)
    reference = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "payments"
        ordering = ["-payment_date"]

    def __str__(self):
        return self.payment_number


class PaymentAllocation(models.Model):
    """
    Read-mostly mapping onto `payment_allocations` — how much of a payment
    was applied to a given client/supplier invoice. Used here purely to
    compute a client's outstanding balance.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_id = models.UUIDField()
    client_invoice_id = models.UUIDField(null=True, blank=True)
    supplier_invoice_id = models.UUIDField(null=True, blank=True)
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        managed = False
        db_table = "payment_allocations"


class ClientDocument(models.Model):
    """
    Read-mostly mapping onto the shared `documents` table, filtered to
    entity_type='client'. Full upload/delete CRUD belongs to the Document
    Management module (Nada).
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


def get_client_financials(client_id):
    """
    Shared helper used by both the Client detail serializer (outstanding
    balance) and the /clients/{id}/balance/ endpoint (full breakdown), so
    the calculation only lives in one place.

    total_invoiced excludes DRAFT and CANCELLED invoices — those aren't
    real receivables yet/anymore.
    outstanding = total_invoiced - total actually allocated against those
    invoices via payment_allocations (not just "payments received", since
    a single payment can be split across multiple invoices).
    """
    invoice_qs = ClientInvoiceSummary.objects.filter(client_id=client_id).exclude(
        status__in=[ClientInvoiceSummary.STATUS_DRAFT, ClientInvoiceSummary.STATUS_CANCELLED]
    )
    total_invoiced = invoice_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")

    total_paid = PaymentAllocation.objects.filter(
        client_invoice_id__in=invoice_qs.values_list("id", flat=True)
    ).aggregate(total=Sum("allocated_amount"))["total"] or Decimal("0.00")

    return {
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "outstanding_balance": total_invoiced - total_paid,
    }