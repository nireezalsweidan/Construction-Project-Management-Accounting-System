"""
Session-based middleware that bridges Django's request.user to the app's
own ``users.User`` model.

The dashboard (``apps.core``) guards pages with Django's ``@login_required``
decorator and templates use ``user.is_authenticated``. By default those only
recognise Django's built-in ``auth.User`` (AUTH_USER_MODEL), which this
project does not use for logins -- authentication happens against the
``users.User`` table, and the login view stores the id under
``users.authentication.SESSION_USER_ID_KEY``.

This middleware runs after Django's ``AuthenticationMiddleware`` and, when
the app session login is present, resolves the logged-in users.User from that
session key and assigns it to ``request.user`` -- even if Django had already
attached a built-in auth.User. That single change makes ``@login_required``,
``request.user.is_authenticated``, ``request.user.is_owner`` /
``request.user.is_accountant``, and the ``user`` template variable all behave
correctly for app users, so server-rendered pages and the DRF API
authenticate the same people.
"""
from .authentication import SESSION_USER_ID_KEY
from .models import User


class AppUserSessionMiddleware:
    """Resolve request.user to the app's users.User from the session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session = getattr(request, 'session', None)
        if session is not None and session.get(SESSION_USER_ID_KEY):
            resolved = self._resolve_from_session(request)
            if resolved is not None:
                request.user = resolved
                return self.get_response(request)
        # No app-session login, but Django's AuthenticationMiddleware may have
        # attached a built-in auth.User (e.g. someone signed in through the
        # Django admin at /admin/ and then navigates to /dashboard/). Bridge it
        # to the app's users.User by matching username so role-based pages such
        # as the dashboard (request.user.is_owner / is_accountant) work.
        current = getattr(request, 'user', None)
        if current is not None and not getattr(current, 'is_anonymous', True):
            app_user = self._resolve_by_username(current)
            if app_user is not None:
                request.user = app_user
        return self.get_response(request)

    def _resolve_from_session(self, request):
        session = getattr(request, 'session', None)
        if session is None:
            return None
        user_id = session.get(SESSION_USER_ID_KEY)
        if user_id is None:
            return None
        try:
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError):
            return None
        if not user.is_active:
            return None
        return user

    def _resolve_by_username(self, django_user):
        """Bridge a Django built-in auth.User to the matching app users.User.

        The ``users`` table is shared and unmanaged (managed=False), so it
        may not exist in every environment/test database -- if it is missing
        or the lookup fails, return None and leave request.user untouched.
        """
        username = getattr(django_user, 'username', None)
        if not username:
            return None
        try:
            user = User.objects.get(username__iexact=username)
        except Exception:
            return None
        if not user.is_active:
            return None
        return user
