"""
DRF serializers for the ``users`` app -- Authentication & Authorization.

Grouped by request type:
- ``LoginSerializer`` / ``ChangePasswordSerializer`` /
  ``RequestPasswordResetSerializer`` / ``ResetPasswordSerializer``: form
  inputs for the auth action endpoints in ``users/views.py``.
- ``UserSerializer`` / ``UserCreateSerializer`` / ``UserUpdateSerializer``:
  user-management (admin registration / profile) serializers.
"""
import re

from rest_framework import serializers

from .models import Role, User
from .services import get_user_from_uid
from .tokens import default_token_generator


def validate_password_strength(value: str) -> str:
    """Minimal password policy: a non-empty password of at least 8 chars."""
    if value is None or len(value) < 8:
        raise serializers.ValidationError("Password must be at least 8 characters long.")
    return value


def _slugify(value: str) -> str:
    """Lowercase, keep letters/digits, collapse whitespace/dashes to a single dash."""
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value


def build_username(first_name: str, last_name: str) -> str:
    """Generate ``firstname-lastname`` (lowercased) from the person's names."""
    base = _slugify(f"{first_name} {last_name}")
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        n += 1
        username = f"{base}-{n}"
    return username


def build_email(first_name: str, last_name: str) -> str:
    """Generate ``firstname.lastname@cedar.com`` from the person's names."""
    local = _slugify(f"{first_name} {last_name}").replace("-", ".")
    base = f"{local}@cedar.com"
    email, n = base, 1
    while User.objects.filter(email__iexact=email).exists():
        n += 1
        email = f"{local}{n}@cedar.com"
    return email


def generate_password() -> str:
    """
    Generate a strong initial password (passes the 8-char policy) for a
    system-created account. Shown to the Owner/admins and emailed to the
    new user once; the user is expected to change it on first login.
    """
    import secrets
    import string as _string
    alphabet = _string.ascii_letters + _string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


class UserSerializer(serializers.ModelSerializer):
    """
    Read/update representation of a user (no password exposure).

    ``role`` and ``is_active`` are shown on read; only the Owner may
    change them (enforced in the viewset via permission classes and
    write-only handling on the create/update serializers below). The
    password is never serialized out.
    """
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'role',
            'role_display', 'phone', 'is_active', 'last_login',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'last_login', 'created_at', 'updated_at']


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Admin/owner registration of a new user.

    This is the ONLY way a user account is created -- there is no public
    sign-up. When the Owner supplies a ``password`` it is hashed via
    ``User.set_password`` (never stored in plaintext). When any of
    ``username`` / ``email`` / ``password`` is omitted they are generated:
    - username -> ``firstname-lastname``
    - email    -> ``firstname.lastname@cedar.com``
    - password -> a strong random password
    and a credentials email is sent to the new user (see ``users.services``
    ``send_account_credentials_email``, triggered from the view).
    """
    password = serializers.CharField(write_only=True, required=False,
                                     validators=[validate_password_strength])

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'role',
            'phone', 'is_active', 'password',
        ]
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
        }

    def validate_role(self, value):
        if value not in Role.values:
            raise serializers.ValidationError(f"role must be one of {list(Role.values)}.")
        return value

    def validate(self, attrs):
        first_name = attrs.get('first_name', '')
        last_name = attrs.get('last_name', '')
        if not first_name or not last_name:
            raise serializers.ValidationError(
                {'first_name': 'first_name and last_name are required.'}
            )
        # Auto-generate username / email from the person's name when absent.
        if not attrs.get('username'):
            attrs['username'] = build_username(first_name, last_name)
        if not attrs.get('email'):
            attrs['email'] = build_email(first_name, last_name)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password', None) or generate_password()
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        user._raw_password = password  # used by the view to email credentials
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Owner updates another user's details / role / status. Password is
    handled by the dedicated password-reset flow, never via this serializer.
    """
    role = serializers.ChoiceField(choices=Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'role', 'is_active']


class LoginSerializer(serializers.Serializer):
    """
    Login input: ``username`` + ``password``. The password is checked
    against ``users.password_hash``. Usernames are matched case-insensitively
    for convenience. Validation does NOT run the login itself -- the view
    does that and sets the session -- but it does verify the credentials
    belong to an active user so the view can rely on it.
    """
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        username = attrs['username']
        password = attrs['password']

        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            user = None

        if user is None or not user.check_password(password):
            raise serializers.ValidationError("Unable to log in with provided credentials.")
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")
        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Change the currently-logged-in user's password."""
    old_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password_strength])

    def __init__(self, *args, **kwargs):
        self._user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        if self._user is None:
            raise serializers.ValidationError("Authentication required.")
        if not self._user.check_password(attrs['old_password']):
            raise serializers.ValidationError("Current password is incorrect.")
        return attrs


class RequestPasswordResetSerializer(serializers.Serializer):
    """
    Forgot-password input: the user submits the ``email`` on their
    account. If it belongs to an active account, an email with a reset
    link is sent (see ``users.services.send_password_reset_email``). The
    response always reports success regardless of whether the email
    matches, so the endpoint cannot be used to enumerate accounts.
    """
    email = serializers.EmailField()

    def validate(self, attrs):
        try:
            self._user = User.objects.get(email__iexact=attrs['email'])
        except User.DoesNotExist:
            self._user = None
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    """
    Complete the password reset. The user opens the emailed link
    (which carries the url-safe ``uid`` and stateless ``token``), enters a
    new password, and posts ``uid`` / ``token`` / ``new_password`` here so
    the token can be validated and the password replaced.

    ``uid`` is the url-safe base64-encoded user pk; ``token`` is the value
    generated by ``default_token_generator`` and sent in the reset email.
    """
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password_strength])

    def validate(self, attrs):
        user = get_user_from_uid(attrs['uid'])
        if user is None or not user.is_active:
            raise serializers.ValidationError("Invalid or expired password reset link.")
        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError("Invalid or expired password reset link.")
        attrs['user'] = user
        return attrs
