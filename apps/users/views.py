"""
DRF views for the ``users`` app -- Authentication & Authorization (RBAC).

Endpoints
---------
Mounted under /api/auth/ (see ``construction/urls.py``):

Auth + account (JWT Bearer token):
- POST   /api/auth/login/                          -> authenticate, return JWT
- POST   /api/auth/logout/                         -> confirm logout (client discards tokens)
- POST   /api/auth/token/refresh/                  -> refresh access token
- GET    /api/auth/me/                             -> own profile
- PATCH  /api/auth/me/                             -> update own profile
- POST   /api/auth/change-password/                -> change own password
- POST   /api/auth/request-password-reset/         -> email forgot-password link
- POST   /api/auth/reset-password/                 -> validate link, set new password

User management (OWNER only; "registration by admin"):
- GET    /api/auth/users/                          -> list users
- POST   /api/auth/users/                          -> create (admin registration)
- GET    /api/auth/users/{id}/                     -> retrieve
- PATCH  /api/auth/users/{id}/                     -> update role/status/details
- DELETE /api/auth/users/{id}/                     -> hard delete (see note)
- POST   /api/auth/users/{id}/activate/            -> activate
- POST   /api/auth/users/{id}/deactivate/          -> deactivate
- POST   /api/auth/users/{id}/reset-password/      -> admin sets a user's password

There is deliberately NO public registration endpoint: the Owner is the
only one who can create accounts (``UserViewSet`` is ``IsOwner``-gated).
"""
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .permissions import IsAuthenticated, IsOwner
from .serializers import (
    ChangePasswordSerializer,
    JwtLoginSerializer,
    RequestPasswordResetSerializer,
    ResetPasswordSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
    validate_password_strength,
)
from .services import send_account_credentials_email
from .services import send_password_reset_email


class AuthView(APIView):
    """Shared auth endpoints grouped into one class-level view set."""

    permission_classes = [IsAuthenticated]

    # --- profile ----------------------------------------------------------

    def get_me(self, request):
        return Response(UserSerializer(request.user).data)

    def patch_me(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # A user may update profile attributes (name/email/phone) but not
        # escalate their own role or deactivate themselves here.
        serializer.validated_data.pop('role', None)
        serializer.validated_data.pop('is_active', None)
        serializer.save()
        return Response(UserSerializer(request.user).data)

    # --- password ---------------------------------------------------------

    def post_change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data, user=request.user)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password_hash', 'updated_at'])
        return Response({'detail': 'Password changed.'}, status=status.HTTP_200_OK)

    def post_request_password_reset(self, request):
        serializer = RequestPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer._user
        if user is not None and user.is_active:
            send_password_reset_email(user)
        return Response({'detail': 'If that email is on an account, a reset link has been sent.'})

    def post_reset_password(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password_hash', 'updated_at'])
        return Response({'detail': 'Password reset successfully.'}, status=status.HTTP_200_OK)


class LoginView(APIView):
    """Authenticate and return JWT access + refresh tokens."""
    permission_classes = []

    def post(self, request):
        serializer = JwtLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Record last_login on the user (nullable TIMESTAMP column).
        from django.utils import timezone
        user = serializer.validated_data['user']
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        return Response(serializer.get_tokens(), status=status.HTTP_200_OK)


class TokenRefreshView(APIView):
    """Refresh an access token using a valid refresh token."""
    permission_classes = []

    def post(self, request):
        from .serializers import CustomTokenRefreshSerializer
        serializer = CustomTokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Confirm logout. Client discards tokens (no server-side blacklist)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'detail': 'Logged out.'}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return AuthView().get_me(request)

    def patch(self, request):
        return AuthView().patch_me(request)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return AuthView().post_change_password(request)


class RequestPasswordResetView(APIView):
    permission_classes = []

    def post(self, request):
        return AuthView().post_request_password_reset(request)


class ResetPasswordView(APIView):
    permission_classes = []

    def post(self, request):
        return AuthView().post_reset_password(request)


class UserViewSet(mixins.CreateModelMixin,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):
    """
    OWNER-only management of user accounts.

    This is the "registration by admin" path: create/update/list/retrieve
    users, activate/deactivate them, and reset their password. Regular
    (non-Owner) users are blocked by ``IsOwner``.
    """
    permission_classes = [IsOwner]
    queryset = User.objects.all()
    search_fields = ['username', 'email', 'first_name', 'last_name', 'role']
    ordering_fields = ['username', 'created_at', 'role', 'is_active']
    ordering = ['created_at']

    def get_serializer_class(self):
        if self.action in ('create',):
            return UserCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UserUpdateSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        headers = self.get_success_headers(serializer.data)
        # Email the new user their login credentials (system-generated or
        # owner-provided password). The owner sees data via the response.
        send_account_credentials_email(user, getattr(user, '_raw_password', ''))
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.id == request.user.id:
            return Response(
                {'detail': 'You cannot delete your own account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=['is_active'])
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user.id == request.user.id:
            return Response(
                {'detail': 'You cannot deactivate your own account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        """
        Owner sets a new password for a user. Body: {new_password}.
        Hashes it via Django's hashers -- no token round-trip needed for
        the admin resetting someone else's account.
        """
        new_password = request.data.get('new_password')
        try:
            validate_password_strength(new_password)
        except Exception:
            raise DRFValidationError({'new_password': 'Password must be at least 8 characters long.'})
        user = self.get_object()
        user.set_password(new_password)
        user.save(update_fields=['password_hash', 'updated_at'])
        return Response({'detail': 'Password reset.'})
