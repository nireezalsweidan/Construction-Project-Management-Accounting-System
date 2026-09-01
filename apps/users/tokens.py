"""
Password-reset token generator for the ``users`` app.

Django's built-in ``PasswordResetTokenGenerator._make_hash_value`` reads
``user.password`` and ``user.get_email_field_name()``. This project's user
model stores the hash in ``password_hash`` (matching the schema's ``users``
table) and is not backed by Django's auth machinery, so we subclass it to
hash on ``password_hash`` and the ``email`` field. Everything else
(timestamped, single-use, invalidated on password change / login, bounded
by ``PASSWORD_RESET_TIMEOUT``) is inherited unchanged.
"""
from django.contrib.auth.tokens import PasswordResetTokenGenerator


class UserPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "users.UserPasswordResetTokenGenerator"

    # The User model's email attribute (used instead of the auth framework's
    # dynamic get_email_field_name()).
    email_field = 'email'

    def _make_hash_value(self, user, timestamp):
        login_timestamp = (
            ""
            if user.last_login is None
            else user.last_login.replace(microsecond=0, tzinfo=None)
        )
        email = getattr(user, self.email_field, "") or ""
        return f"{user.pk}{user.password_hash}{login_timestamp}{timestamp}{email}"


default_token_generator = UserPasswordResetTokenGenerator()
