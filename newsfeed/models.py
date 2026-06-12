from django.conf import settings
from django.db import models
from django.utils import timezone


class NewsFeedEntry(models.Model):
    class EntryType(models.TextChoices):
        RECIPE_PUBLISHED = "recipe_published", "Recipe Published"
        ARTICLE_PUBLISHED = "article_published", "Article Published"
        AMUSE_BOUCHE_PUBLISHED = "amuse_bouche_published", "Amuse-Bouche Published"
        AMUSE_BOUCHE_FEATURED = "amuse_bouche_featured", "Amuse-Bouche Featured"
        SITE_UPDATE = "site_update", "Site Update"
        SECURITY_UPDATE = "security_update", "Security Update"
        VERSION_RELEASE = "version_release", "Version Release"
        ADMIN_NOTE = "admin_note", "Admin Note"
        BATTLE_EVENT = "battle_event", "Chef Battle Event"

    entry_type = models.CharField(
        max_length=30,
        choices=EntryType.choices,
        db_index=True,
    )
    title = models.CharField(max_length=300)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    published_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_auto = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    version = models.CharField(max_length=30, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="newsfeed_entries",
    )
    image_url = models.CharField(max_length=500, blank=True)
    # Null for manual entries; unique string for auto entries prevents duplicates.
    event_key = models.CharField(max_length=200, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["-published_at"]
        verbose_name = "News Feed Entry"
        verbose_name_plural = "News Feed Entries"

    def __str__(self):
        return f"[{self.get_entry_type_display()}] {self.title}"


class SocialPostLog(models.Model):
    class Platform(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    platform = models.CharField(max_length=30, choices=Platform.choices, db_index=True)
    event_key = models.CharField(max_length=200, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    target_url = models.CharField(max_length=500, blank=True)
    message = models.TextField(blank=True)
    response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["platform", "event_key"], name="unique_social_post_event"),
        ]
        verbose_name = "Social post log"
        verbose_name_plural = "Social post logs"

    def __str__(self):
        return f"{self.platform}:{self.event_key} ({self.status})"
