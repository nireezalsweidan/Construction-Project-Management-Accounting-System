"""
Business logic for the ``users`` app -- Authentication & Authorization.

Centralizes the password / password-reset logic that must not be scattered
across serializers and viewsets, following the same pattern as
``purchasing.services`` and ``inventory.services``: a business rule is a
single, explicitly-called function so it can't be silently bypassed.

Concerns here:
1. Password hashing is always done via Django's hashers on the existing
   ``password_hash`` column (``User.set_password`` / ``User.check_password``
   do this) -- never stored as plaintext.
2. Password reset uses Django's built-in, stateless
   ``PasswordResetTokenGenerator`` (see ``users.tokens``). A token is
   derived from the user's pk + password hash + last_login + a timestamp,
   sent by email via SMTP (forgot-password flow), validated by the
   ``reset-password`` endpoint, and invalidated as soon as the password
   changes. No columns are needed on the shared ``users`` table.
3. Admin registration emails the new user their login credentials (there
   is no public sign-up; the Owner adds accounts).
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import User
from .tokens import default_token_generator

_RESET_BUTTON_HTML = """\
<div style="margin:18px 0;text-align:center;">
  <a href="{reset_url}"
     style="background-color:#1a73e8;color:#ffffff;text-decoration:none;
            padding:12px 28px;border-radius:6px;font-size:15px;
            font-weight:600;display:inline-block;">
     Reset Password
  </a>
</div>
"""


def _camel_to_words(value: str) -> str:
    """Humanize a generated username for display in emails (e.g. first-user -> First User)."""
    words = value.replace('-', ' ').replace('_', ' ').strip().split()
    return ' '.join(w.capitalize() for w in words if w)


def send_password_reset_email(user) -> None:
    """
    Email ``user`` an HTML reset email with a clickable "Reset Password"
    button linking to the configured reset page (``PASSWORD_RESET_BASE_URL``)
    plus the url-safe uid and token.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f"{settings.PASSWORD_RESET_BASE_URL}?uid={uidb64}&token={token}"

    text = (
        "You're receiving this email because a password reset was "
        f"requested for your account ({user.username}).\n\n"
        f"Open the link below to choose a new password:\n{reset_url}\n\n"
        "If you did not request this, you can safely ignore this email."
    )
    html = (
        "<p>You're receiving this email because a password reset was "
        f"requested for your account (<strong>{user.username}</strong>).</p>"
        "<p>Click the button below to choose a new password:</p>"
        + _RESET_BUTTON_HTML.format(reset_url=reset_url) +
        "<p>If you did not request this, you can safely ignore this email.</p>"
    )
    _send_email(
        subject="Reset your password",
        text=text,
        html=html,
        recipient=user.email,
    )


def send_account_credentials_email(user, raw_password: str) -> None:
    """
    Email a just-created user their login credentials (username + password).

    There is no public registration: the Owner creates accounts, so this is
    how a new user learns how to log in. Only the username is shown in the
    formatting; the raw (one-time shown) password is included for the user.
    """
    display_name = _camel_to_words(user.username) or user.first_name
    text = (
        f"Hello {display_name},\n\n"
        f"An account has been created for you on the Cedar system.\n\n"
        f"Username: {user.username}\n"
        f"Password: {raw_password}\n\n"
        "Please log in and change your password as soon as possible.\n\n"
        "This email contains your login credentials. Do not share it."
    )
    html = (
        f"<p>Hello <strong>{display_name}</strong>,</p>"
        "<p>An account has been created for you on the Cedar system.</p>"
        "<p><strong>Username:</strong> {username}<br>"
        "<strong>Password:</strong> {password}</p>"
        "<p>Please log in and change your password as soon as possible.</p>"
        "<p style='color:#666;font-size:13px;'>This email contains your "
        "login credentials. Do not share it.</p>"
    ).format(username=user.username, password=raw_password)
    _send_email(
        subject="Your Cedar account credentials",
        text=text,
        html=html,
        recipient=user.email,
    )


def _send_email(*, subject: str, text: str, html: str, recipient: str) -> None:
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)


def get_user_from_uid(uid: str):
    """
    Resolve the ``users.User`` from a url-safe base64-encoded uid. Returns
    None for malformed/unrecognised uids (design error, not a 500).
    """
    try:
        return User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None

