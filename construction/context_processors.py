"""
Shared template context processors (CPMAS-58).

``app_user`` bridges a bit of a real architecture gap: the dashboard
(``apps.core``) authenticates against Django's built-in ``auth.User``
(session login via ``/accounts/login/``), while the domain API
(``users.User`` -- FKs like ``Notification.user``) is a separate model
authenticated via ``/api/auth/login/``. Nothing currently links a
logged-in dashboard session to a specific ``users.User`` row.

Until that's unified (a cross-cutting auth change well beyond this
ticket), this resolves the best available bridge -- a ``users.User``
row whose ``username`` matches the Django session's username -- so
per-user frontend widgets (the notifications bell) have *something* to
scope requests by. When no matching row exists, ``app_user_id`` is
simply empty and those widgets degrade to an empty state rather than
erroring.

Runs on every authenticated template render project-wide (it's a
context processor, not scoped to one app), so the ``users`` table not
existing is treated the same way -- e.g. a test rendering an
authenticated page without ``users.testing.WithUsersTableMixin`` (most
don't, since most pages have nothing to do with this bridge) shouldn't
start failing because of a widget it never asked for.
"""
from django.db.utils import DatabaseError

from users.models import User as AppUser


def app_user(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"app_user_id": None}

    try:
        app_user_row = AppUser.objects.filter(username=user.get_username()).first()
    except DatabaseError:
        return {"app_user_id": None}
    return {"app_user_id": str(app_user_row.id) if app_user_row else None}
