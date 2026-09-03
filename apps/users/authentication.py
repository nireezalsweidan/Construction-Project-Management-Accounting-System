"""
Custom DRF authentication for the ``users`` app.

Provides two authentication backends:

1. ``UserSessionAuthentication`` — resolves ``request.user`` from the
   Django session via the custom ``users.User`` table.  Used for
   server-rendered pages where the session cookie is the auth mechanism.

2. ``JwtUserAuthentication`` — a ``simplejwt.JWTAuthentication`` subclass
   that looks up ``users.User`` (UUID PK) instead of Django's default
   ``auth.User`` (integer PK).  Used as the DRF default for API calls.
"""
from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import (
    JWTAuthentication as _SimpleJwtAuth,
)

from .models import Role, User

# Session key under which we store the logged-in user's id. Distinct from
# the built-in "_auth_user_id" Django uses so we never collide with, or
# pretend to be, a Django auth.User session.
SESSION_USER_ID_KEY = '_users_user_id'


def _csrf_required(request) -> bool:
    """
    Whether CSRF enforcement should apply for this request.

    CSRF is enforced for authenticated sessions on unsafe methods (DRF's
    standard behaviour). When Django is running with DEBUG=True the check
    is relaxed so local development / API clients (e.g. Thunder Client,
    Postman) can exercise the flow without manually forwarding the
    csrftoken cookie.  This NEVER weakens production: DEBUG=False keeps
    CSRF fully enforced.
    """
    return not getattr(settings, 'DEBUG', False)


class UserSessionAuthentication(SessionAuthentication):
    """
    Resolve ``request.user`` from the Django session via users.User id.

    Behaves like DRF's SessionAuthentication (CSRF-protected, relies on the
    session cookie) but reads our own session key and models an
    authenticated ``users.User``.  Used for server-rendered pages.
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
            user = self._resolve_from_session(request)

        if user is None or getattr(user, 'is_anonymous', True) or not user.is_active:
            return None

        if _csrf_required(request):
            self.enforce_csrf(request)

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
        return 'Session'


class JwtUserAuthentication(_SimpleJwtAuth):
    """
    JWT authentication that resolves against ``users.User`` instead of
    ``AUTH_USER_MODEL``.

    simplejwt's default ``JWTAuthentication.get_user()`` calls
    ``get_user_model().objects.get(**{pk_field: user_id})``.  Because
    ``users.User`` is NOT ``AUTH_USER_MODEL``, that lookup fails with
    integer/UUID type mismatches.  This subclass overrides ``get_user``
    to query our custom model directly.
    """

    def get_user(self, validated_token):
        user_id = validated_token.get('user_id')
        if user_id is None:
            return None
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
