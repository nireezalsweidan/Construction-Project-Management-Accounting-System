"""
Custom DRF authentication for the ``users`` app.

Django's ``SessionAuthentication`` (and the existing ``IsAuthenticated``
defaults in ``construction/settings.py``) relies on Django's session
middleware setting ``request.user`` to an authenticated ``auth.User``.
Because this project authenticates against its own ``users.User`` table
instead of the built-in Auth model (see ``users.models``), we provide a
session-based subclass that resolves the logged-in user from the Django
session by ID and returns that ``users.User`` instance as ``request.user``.
"""
from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework.authentication import SessionAuthentication

from .models import Role, User

# Session key under which we store the logged-in user's id. Distinct from
# the built-in "_auth_user_id" Django uses so we never collide with, or
# pretend to be, a Django auth.User session.
SESSION_USER_ID_KEY = '_users_user_id'


def _csrf_required(request) -> bool:
    """
    Whether CSRF enforcement should apply for this request.

    CSRF is enforced for authenticated sessions on unsafe methods (DRF's
    standard behaviour). When Django is running with DEBUG=True the check is
    relaxed so local development / API clients (e.g. Thunder Client, Postman)
    can exercise the flow without manually forwarding the csrftoken cookie.
    This NEVER weakens production: DEBUG=False keeps CSRF fully enforced.
    """
    return not getattr(settings, 'DEBUG', False)


class UserSessionAuthentication(SessionAuthentication):
    """
    Resolve ``request.user`` from the Django session via users.User id.

    Behaves like DRF's SessionAuthentication (CSRF-protected, relies on the
    session cookie) but reads our own session key and models an
    authenticated ``users.User``. Used as the DEFAULT_AUTHENTICATION_CLASSES
    authentication backend for the API.
    """

    def authenticate(self, request):
        user = getattr(request._request, 'user', None)

        # Dashboard pages use Django's login view. When that authenticated
        # web account has a matching application user, resolve the latter so
        # role-aware APIs see OWNER/ACCOUNTANT and financial FK attribution
        # uses the schema-backed users table.
        if user and not getattr(user, 'is_anonymous', True):
            web_user = user
            try:
                user = User.objects.get(username=user.username, is_active=True)
            except User.DoesNotExist:
                user = self._finance_identity_for_web_user(web_user)

        if not user or not getattr(user, 'is_active', False):
            # Django's auth middleware only recognizes AUTH_USER_MODEL, so a
            # logged-in users.User is not attached automatically -- resolve
            # it from the Django session (set by the login view).
            user = self._resolve_from_session(request)

        if user is None or getattr(user, 'is_anonymous', True) or not user.is_active:
            return None

        # Preserve DRF's SessionAuthentication behaviour: an authenticated
        # session requires a valid CSRF token on unsafe methods, so a CSRF
        # token in a script isn't enough to act as that user. Relaxed only in
        # DEBUG for local API-client testing (see _csrf_required).
        if _csrf_required(request):
            self.enforce_csrf(request)

        # Attach the resolved user back to the wrapped request so the rest
        # of DRF (permissions, request.user, throttling) sees it.
        request._request.user = user
        return user, None

    @staticmethod
    def _finance_identity_for_web_user(web_user):
        """Bridge Django administrators to the schema-backed OWNER role.

        The dashboard historically used Django's auth table while APIs use
        the SQL-source-of-truth ``users`` table. A Django superuser is the
        dashboard's Owner equivalent, so ensure it has a matching API
        identity. Ordinary Django users are left unchanged and therefore do
        not gain finance permissions.
        """
        if not getattr(web_user, 'is_superuser', False):
            return web_user

        email = (getattr(web_user, 'email', '') or '').strip()
        if email:
            existing = User.objects.filter(email__iexact=email, is_active=True).first()
            if existing is not None:
                return existing

        try:
            with transaction.atomic():
                return User.objects.create(
                    username=web_user.username,
                    email=email or f'{web_user.username}@dashboard.local',
                    password_hash=web_user.password,
                    first_name=web_user.first_name or 'Dashboard',
                    last_name=web_user.last_name or 'Owner',
                    role=Role.OWNER,
                    is_active=True,
                )
        except IntegrityError:
            # A simultaneous first request may have created it already.
            return User.objects.get(username=web_user.username, is_active=True)

    def _resolve_from_session(self, request):
        session = getattr(request._request, 'session', None)
        if session is None:
            return None
        user_id = session.get(SESSION_USER_ID_KEY)
        if user_id is None:
            return None
        try:
            return User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError):
            return None

    def authenticate_header(self, request):
        # Returning a non-empty scheme makes DRF emit 401 (with a
        # WWW-Authenticate header) for unauthenticated requests rather than
        # 403, matching the API-desired "you must be logged in" semantics.
        return 'Session'
