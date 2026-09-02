"""
Session-based middleware that bridges Django's request.user to the app's
own ``users.User`` model.

The dashboard (``apps.core``) guards pages with Django's ``@login_required``
decorator and templates use ``user.is_authenticated``. By default those only
recognise Django's built-in ``auth.User`` (AUTH_USER_MODEL), which this
project does not use for logins -- authentication happens against the
``users.User`` table, and the login view stores the id under
``users.authentication.SESSION_USER_ID_KEY``.

This middleware runs after Django's ``AuthenticationMiddleware`` and, when no
authenticated auth.User is attached, resolves the logged-in users.User from
that session key and assigns it to ``request.user``. That single change makes
``@login_required``, ``request.user.is_authenticated``, and the ``user``
template variable all behave correctly for app users, so server-rendered
pages and the DRF API authenticate the same people.
"""
from .authentication import SESSION_USER_ID_KEY
from .models import User


class AppUserSessionMiddleware:
    """Resolve request.user to the app's users.User from the session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is None or getattr(user, 'is_anonymous', False):
            resolved = self._resolve_from_session(request)
            if resolved is not None:
                request.user = resolved
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
