"""
Shared template context processors (CPMAS-58).

``app_user`` exposes the logged-in ``users.User``'s id as
``app_user_id``, for frontend widgets (the notifications bell) that
need to scope API requests to "the current user".

``users.middleware.AppUserSessionMiddleware`` now resolves
``request.user`` to a real ``users.User`` for the normal dashboard
login path (``/accounts/login/``), so the common case is just reading
``request.user.id`` directly. The one remaining gap is legacy/test
paths that still authenticate via Django's own ``auth.User`` (e.g.
``self.client.login()`` in older tests) -- AppUserSessionMiddleware
only bridges an *anonymous* request, so an already-authenticated
auth.User is left as-is. For that case only, fall back to a
``users.User`` row whose ``username`` matches, degrading to no bridge
(``app_user_id: None``) rather than erroring when nothing matches.

Runs on every authenticated template render project-wide (it's a
context processor, not scoped to one app), so the ``users`` table not
existing is treated the same way -- a test rendering an authenticated
page without ``users.testing.WithUsersTableMixin`` (most don't, since
most pages have nothing to do with this bridge) shouldn't start
failing because of a widget it never asked for.
"""
from django.db.utils import DatabaseError

from users.models import User as AppUser


def app_user(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"app_user_id": None}

    # The common case: AppUserSessionMiddleware already resolved
    # request.user to a real users.User.
    if isinstance(user, AppUser):
        return {"app_user_id": str(user.id)}

    # Fallback for a still-plain auth.User (legacy/test login paths).
    try:
        app_user_row = AppUser.objects.filter(username=user.get_username()).first()
    except DatabaseError:
        return {"app_user_id": None}
    return {"app_user_id": str(app_user_row.id) if app_user_row else None}
