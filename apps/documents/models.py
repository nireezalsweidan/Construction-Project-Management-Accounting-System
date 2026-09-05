"""
Models for the ``documents`` app -- Document Management (CPMAS-25).

Implements ``Document``, the real owner of the shared ``documents`` table
(BRD: "Upload and associate contracts, invoices, receipts, POs, change
orders with the relevant entity"). Several other apps (clients, contractors,
projects) already ship a read-only ``managed=False`` mirror of this same
table, scoped to their own ``entity_type`` (e.g. ``ClientDocument``,
``ContractorDocument``, ``ProjectDocument``) purely so their own APIs can
list documents linked to one of their records -- this is the app that
actually owns creation/upload/deletion. Those mirrors and this model can
coexist on the same ``db_table`` without Django's managed-model conflict
check (E028) firing, since only one of them (this one) is ``managed=True``.

``entity_type``/``entity_id`` is a generic pointer (not a real FK) --
same pattern already used by ``notifications.Notification`` elsewhere in
this codebase -- since a document can attach to records in many different
apps (clients, suppliers, contractors, projects, purchase orders, expenses,
invoices, change orders) with no single table to point a FK at.
"""
import uuid

from django.db import models


class Document(models.Model):
    """
    A file uploaded and associated with some other entity in the system.

    Matches the ``documents`` table exactly. ``file_path`` stores the path
    under ``MEDIA_ROOT`` (served via ``MEDIA_URL``) rather than the raw
    uploaded file object, so this stays a plain reflection of the schema's
    column instead of a Django-managed ``FileField`` migration owning its
    own upload_to logic -- the serializer is what actually writes the file
    to storage; see ``DocumentSerializer.create``.
    """

    # entity_type values this app recognises today -- covers every entity
    # the BRD calls out (contracts/invoices/receipts/POs/change orders) via
    # its owning record. Not DB-enforced (the live schema has no CHECK
    # constraint on this column), just validated in the serializer so a
    # typo doesn't silently create an unfindable document.
    ENTITY_TYPES = [
        'client', 'supplier', 'contractor', 'project', 'purchase_order',
        'expense', 'client_invoice', 'supplier_invoice', 'change_order',
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT: who uploaded a document is part of its audit trail and
    # shouldn't be erasable by deleting their user record -- same
    # reasoning as PurchaseOrder.created_by. db_constraint=False: several
    # OTHER apps' read-only managed=False mirrors of this same shared
    # `documents` table (ClientDocument, ContractorDocument,
    # ProjectDocument) model this column as a bare UUIDField with no FK
    # at all, and insert test rows with UUIDs that don't correspond to a
    # real users.User row in their own, unrelated test suites -- a real
    # DB-level FK constraint here would break every one of those. The
    # live schema already declares `uploaded_by UUID NOT NULL REFERENCES
    # users(id)` directly in Postgres, so referential integrity is still
    # enforced where it actually matters; this only skips Django ever
    # trying to (re)create that constraint itself.
    uploaded_by = models.ForeignKey(
        'users.User', on_delete=models.PROTECT, related_name='documents_uploaded',
        db_column='uploaded_by', db_constraint=False,
    )

    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_type = models.CharField(max_length=100, blank=True, null=True)
    file_size = models.BigIntegerField(blank=True, null=True)
    document_type = models.CharField(max_length=100, blank=True, null=True)

    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField()

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'documents'
        ordering = ['-uploaded_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        # No Meta.indexes here for (entity_type, entity_id) -- the live
        # schema already has idx_documents_entity covering exactly that;
        # redeclaring it would just create a redundant duplicate index.

    def __str__(self):
        return self.file_name
