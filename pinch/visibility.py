from django.conf import settings


def can_view_pinch_public_area(user) -> bool:
    if getattr(settings, "PINCH_PUBLIC", False):
        return True

    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True

    try:
        from accounts.views import is_moderator
        return is_moderator(user)
    except Exception:
        return False
