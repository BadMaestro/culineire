"""Sign in with the username written in any case.

The Owner's rule, 2026-07-29: `crestedten`, `CrestedTen` and `CrEsTeDtEn` are one
person, and the login form must not care which one they typed. Django's stock
`ModelBackend` compares the username exactly, so a capital letter remembered
wrongly reads as "invalid username or password" — indistinguishable, to the
person typing, from a forgotten password.

Only the LOOKUP is case-insensitive. The stored username keeps the case it was
registered with, because that is the name the person chose and the site displays
it. The password stays case-sensitive, as passwords must.

The ambiguity this could create — two accounts differing only in case, both
matching one login — is closed at the other end, in `SignUpForm.clean_username`:
a new username that collides case-insensitively with an existing one is refused.
Verified on production 2026-07-29 before this shipped: 20 users, zero collisions,
so no live account changed meaning.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveModelBackend(ModelBackend):
    """`ModelBackend`, but the username is matched without regard to case."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD

        if username is None:
            username = kwargs.get(username_field)
        if username is None or password is None:
            return None

        try:
            user = user_model._default_manager.get(
                **{f"{username_field}__iexact": username}
            )
        except user_model.DoesNotExist:
            # Run the hasher anyway. Returning early here would make a missing
            # account measurably faster than a wrong password, which is how an
            # attacker enumerates who exists. This mirrors ModelBackend.
            user_model().set_password(password)
            return None
        except user_model.MultipleObjectsReturned:
            # Should be unreachable: signup refuses case-variant duplicates and
            # production had none when this shipped. If it ever happens — data
            # imported around the form, say — an exact match is the only honest
            # reading of what the person typed. Guessing between two accounts
            # would be worse than refusing.
            try:
                user = user_model._default_manager.get(**{username_field: username})
            except user_model.DoesNotExist:
                user_model().set_password(password)
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
