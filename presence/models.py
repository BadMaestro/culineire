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
        """Return an event type for the owner, or None for everyone else.

        This announcement belongs to one account. It is how GreenBear tells the
        whole site he has arrived, and the owner has never granted it to anyone
        else: "это его уникальная способность оповестить весь сайт" (2026-07-20).

        It had been widened to fire for staff, superusers and bearseekers as
        well, so a bearseeker signing in raised the same popup and looked, to
        the owner, exactly like someone signing in as him. The ADMIN type is
        kept only so rows already in the table still render; nothing creates a
        new one.

        Do not add branches here. Anything touching GreenBear's account or his
        presence on the site is the owner's decision alone.
        """
        if not user or not getattr(user, "is_authenticated", False):
            return None
        author = getattr(user, "recipe_author_profile", None)
        if author and author.slug == settings.OWNER_SLUG:
            return cls.OWNER
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
        cooldown_cutoff = timezone.now() - datetime.timedelta(
            minutes=getattr(settings, "PRESENCE_EVENT_COOLDOWN_MINUTES", 5)
        )
        already_fired = cls.objects.filter(
            event_type=event_type,
            created_at__gte=cooldown_cutoff,
        ).exists()
        if already_fired:
            return None
        return cls.objects.create(event_type=event_type, triggered_by=user)


class MaintenanceNote(models.Model):
    display_name = models.CharField(max_length=40, blank=True)
    message = models.CharField(max_length=240)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    ip_hash = models.CharField(max_length=64, blank=True, db_index=True)
    user_agent = models.CharField(max_length=180, blank=True)
    is_visible = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def name_or_guest(self):
        return self.display_name or "Guest"

    def __str__(self):
        return f"{self.name_or_guest}: {self.message[:48]}"
