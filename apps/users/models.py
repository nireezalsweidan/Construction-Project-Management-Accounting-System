"""
Models for the ``users`` app -- Authentication & Authorization (RBAC).

This module becomes the home of the real Users/RBAC implementation
(per the schema's ``users`` and ``permissions`` tables), taking over the
``users`` table that earlier tickets only referenced as an FK target.

Design notes
------------
The live database's ``users`` table (provisioned directly from the
canonical schema, see docs/schema/README.md) stores ``role`` as a plain
VARCHAR with values like OWNER / ACCOUNTANT, and ``is_active`` as a bool
flag -- there are NO ``groups`` / ``user_permissions`` / ``is_staff`` /
``is_superuser`` columns. This is not Django's many-to-many Group/Permission
RBAC; it is a role-flag on the user plus role-based DRF permission classes
(see ``users.permissions`` and ``users.policies``).

This app deliberately does NOT point Auth at Django's built-in model by
changing ``AUTH_USER_MODEL``: that would break against a shared, already
migrated database (the ``auth`` app's migrations have long been applied
here with the default ``auth.User`` -- see ``showmigrations``), so instead
authentication is implemented directly against this ``users.User`` model
(see ``users.authentication`` / ``users.views``), using Django's own
password-hashing and session machinery for the heavy lifting.

Schema-faithfulness
-------------------
The ``users`` table already exists and is owned by the schema. ``managed
= False`` keeps the full lifecycle with the SQL source of truth, exactly
as before. No columns are added: password-reset tokens are stateless
(Django's ``PasswordResetTokenGenerator`` derives them from the user's pk,
password hash, and last_login -- see ``users.tokens``), so the shared
``users`` table needs no schema change for this ticket.
"""
import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class Role(models.TextChoices):
    """Role values used by RBAC. Stored as-is in ``users.role`` (VARCHAR)."""
    OWNER = 'OWNER', 'Owner'
    ACCOUNTANT = 'ACCOUNTANT', 'Accountant'


class User(models.Model):
    """
    The application's user, backed by the existing ``users`` table.

    Authentication is implemented against this model (see
    ``users.authentication`` and ``users.views``) using Django's password
    hashers writing to the existing ``password_hash`` column. Fields mirror
    the schema's ``users`` table exactly.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, choices=Role.choices)
    phone = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name', 'role']

    class Meta:
        managed = False
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.username

    # --- password helpers (schema stores it as password_hash) ------------

    def set_password(self, raw_password):
        """Hash ``raw_password`` into the existing ``password_hash`` column."""
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password) -> bool:
        """Return True if ``raw_password`` matches this user's hash."""
        return check_password(raw_password, self.password_hash)

    # --- RBAC helpers -----------------------------------------------------

    @property
    def is_owner(self) -> bool:
        return self.role == Role.OWNER

    @property
    def is_accountant(self) -> bool:
        return self.role == Role.ACCOUNTANT

    # Minimal duck-typed attributes DRF's request.user / generic views and
    # the auth framework touch; they are not stored on the users table (only
    # is_active/role are, and those map to real columns above).
    @property
    def is_anonymous(self) -> bool:
        return False

    @property
    def is_authenticated(self) -> bool:
        return True
