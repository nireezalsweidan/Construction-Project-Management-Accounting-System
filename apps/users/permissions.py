"""
Role-based access control (RBAC) permission classes for the ``users`` app.

These DRF permission classes gate endpoints by the role stored in
``users.role`` (OWNER / ACCOUNTANT). The schema models RBAC as a role flag
on the user, not Django groups/permissions, so each class checks the role
attributes exposed on ``users.User`` (``is_owner`` / ``is_accountant``).

Usage: set ``permission_classes`` on a viewset/action, e.g. an Owner-only
user-management viewset uses ``[IsOwner]``, while endpoints any logged-in
user may call (profile, change password) use ``[IsAuthenticated]``.

Each role class defines both ``has_permission`` (class-level) and a no-op
``has_object_permission``, because DRF's viewset ``get_object()`` invokes
``check_object_permissions`` on every permission. Since ``has_permission``
already enforces the role at the collection level, the object-level check
has nothing extra to forbid -- it just returns True so existing visitors
aren't double-blocked and DRF never sees a missing attribute.

Note on ``IsAuthenticated``: DRF's bundled ``IsAuthenticated`` checks
``request.user and request.user.is_authenticated``. Our custom
authentication returns a real ``users.User`` with ``is_authenticated``
True for logged-in users and ``None`` for guests, so the bundled class
works unchanged -- but we re-export a local alias so callers stay within
this module's vocabulary and we can extend common behavior if needed.
"""
from rest_framework.permissions import IsAuthenticated as _DRFIsAuthenticated

# Re-export with our own name so callers don't import DRF directly.
IsAuthenticated = _DRFIsAuthenticated


class IsOwner:
    """
    Allow only authenticated users whose role is OWNER.

    The Owner is the application administrator: only the Owner may create
    (register) users, deactivate/activate them, or reset their passwords
    (see ``UserViewSet`` in ``users/views.py``).
    """

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        return bool(
            user is not None
            and not getattr(user, 'is_anonymous', True)
            and getattr(user, 'is_owner', False)
        )

    def has_object_permission(self, request, view, obj):
        # Role is fully enforced by has_permission; nothing extra to forbid
        # at the object level.
        return True


class IsAccountant:
    """Allow only authenticated users whose role is ACCOUNTANT."""

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        return bool(
            user is not None
            and not getattr(user, 'is_anonymous', True)
            and getattr(user, 'is_accountant', False)
        )

    def has_object_permission(self, request, view, obj):
        return True
