from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    from .models import PresenceEvent
    PresenceEvent.fire(user)
