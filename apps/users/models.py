"""
Models for the ``users`` app.

The live database already has a ``users`` table (provisioned directly via
SQL, matching the approved schema) that other apps' foreign keys point at
-- e.g. ``inventory.StockMovement.user`` (BRD 5.13/11: every stock
movement and audit action records who performed it). The real custom
User + RBAC implementation is a separate, not-yet-built ticket owned by
someone else.

This file defines ONLY a minimal, unmanaged reflection of that existing
table -- just enough for other apps to declare a real foreign key against
it. ``managed = False`` means Django will never attempt to create, alter,
or drop this table; ownership of its actual lifecycle stays with the
Users/RBAC ticket. That ticket's implementation should replace this class
outright (or flip managed=True once it takes over the table) rather than
extend it.
"""
import uuid

from django.db import models


class User(models.Model):
    """
    Read/reference-only reflection of the existing ``users`` table.

    Field set mirrors the schema's ``users`` table exactly. Not used for
    Django authentication (no password hashing integration, no
    permissions/groups) -- that belongs to the real Users/RBAC model.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    phone = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.username
