import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone


class PresenceEvent(models.Model):
    OWNER = "owner"
    ADMIN = "admin"
    TYPE_CHOICES = [(OWNER, "Owner"), (ADMIN, "Admin")]

    event_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="presence_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def message(self):
        if self.event_type == self.OWNER:
            return "IDDQD — (Bear)seeker Mode On"
        return "(Bear)seeker privileges granted"

    @classmethod
    def resolve_event_type(cls, user):
        """Return event type for a user, or None if not privileged."""
        if not user or not getattr(user, "is_authenticated", False):
            return None
        author = getattr(user, "recipe_author_profile", None)
        if author and author.slug == settings.OWNER_SLUG:
            return cls.OWNER
        if user.is_staff or user.is_superuser:
            return cls.ADMIN
        if author and getattr(author, "has_bearseeker_privileges", False):
            return cls.ADMIN
        return None

    @classmethod
    def fire(cls, user):
        """
        Create a presence event for the user if privileged and not in cooldown.
        5-minute cooldown per role prevents spam on repeated logins.
        """
        event_type = cls.resolve_event_type(user)
        if not event_type:
            return None
        cooldown_cutoff = timezone.now() - datetime.timedelta(minutes=5)
        already_fired = cls.objects.filter(
            event_type=event_type,
            created_at__gte=cooldown_cutoff,
        ).exists()
        if already_fired:
            return None
        return cls.objects.create(event_type=event_type, triggered_by=user)
