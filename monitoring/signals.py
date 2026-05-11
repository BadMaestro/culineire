from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db import DatabaseError
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    del sender, kwargs
    try:
        from monitoring.models import UserActivity
        from monitoring.tracker import get_client_ip, hash_ip

        UserActivity.objects.create(
            user=user,
            session_key=(request.session.session_key or "") if hasattr(request, "session") else "",
            event_type=UserActivity.EventType.LOGIN,
            ip_hash=hash_ip(get_client_ip(request)),
            path=request.path[:500],
        )
    except (AttributeError, DatabaseError, ImportError):
        pass


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    del sender, kwargs
    try:
        from monitoring.models import UserActivity
        from monitoring.tracker import get_client_ip, hash_ip

        UserActivity.objects.create(
            user=user,
            session_key=(request.session.session_key or "") if hasattr(request, "session") else "",
            event_type=UserActivity.EventType.LOGOUT,
            ip_hash=hash_ip(get_client_ip(request)),
            path=request.path[:500],
        )
    except (AttributeError, DatabaseError, ImportError):
        pass


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):
    del sender, kwargs
    try:
        from monitoring.models import SecurityEvent, UserActivity
        from monitoring.tracker import get_client_ip, hash_ip

        ip_hash = hash_ip(get_client_ip(request))
        path = request.path[:500] if request else ""
        ua = request.META.get("HTTP_USER_AGENT", "")[:300] if request else ""

        from monitoring.middleware import _failed_login_severity
        SecurityEvent.objects.create(
            event_type=SecurityEvent.EventType.FAILED_LOGIN,
            severity=_failed_login_severity(ip_hash),
            ip_hash=ip_hash,
            path=path,
            user_agent=ua,
            metadata={"username": credentials.get("username", "")[:100]},
        )
        UserActivity.objects.create(
            event_type=UserActivity.EventType.FAILED_LOGIN,
            ip_hash=ip_hash,
            path=path,
            metadata={"username": credentials.get("username", "")[:100]},
        )
    except (AttributeError, DatabaseError, ImportError):
        pass


def _connect_profile_update():
    try:
        from recipes.models import RecipeAuthor

        @receiver(post_save, sender=RecipeAuthor)
        def on_profile_update(sender, instance, created, **kwargs):
            del sender, kwargs
            if created:
                return
            try:
                from monitoring.models import UserActivity

                user = instance.user
                if user:
                    UserActivity.objects.create(
                        user=user,
                        event_type=UserActivity.EventType.PROFILE_UPDATE,
                        object_type="author",
                        object_id=instance.pk,
                        object_title=instance.name[:255],
                    )
            except (AttributeError, DatabaseError, ImportError):
                pass

    except ImportError:
        pass


def _connect_registration():
    from django.contrib.auth import get_user_model

    user_model = get_user_model()

    @receiver(post_save, sender=user_model)
    def on_user_created(sender, instance, created, **kwargs):
        del sender, kwargs
        if not created:
            return
        try:
            from monitoring.models import UserActivity

            UserActivity.objects.create(
                user=instance,
                event_type=UserActivity.EventType.REGISTER,
                object_type="user",
                object_id=instance.pk,
                object_title=instance.username,
            )
        except (DatabaseError, ImportError):
            pass


_connect_profile_update()
_connect_registration()
