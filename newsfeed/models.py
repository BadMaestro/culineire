from django.conf import settings
from django.db import models
from django.utils import timezone


class NewsFeedEntry(models.Model):
    class EntryType(models.TextChoices):
        RECIPE_PUBLISHED = "recipe_published", "Recipe Published"
        ARTICLE_PUBLISHED = "article_published", "Article Published"
        SITE_UPDATE = "site_update", "Site Update"
        SECURITY_UPDATE = "security_update", "Security Update"
        VERSION_RELEASE = "version_release", "Version Release"
        ADMIN_NOTE = "admin_note", "Admin Note"

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
    # Null for manual entries; unique string for auto entries prevents duplicates.
    event_key = models.CharField(max_length=200, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["-published_at"]
        verbose_name = "News Feed Entry"
        verbose_name_plural = "News Feed Entries"

    def __str__(self):
        return f"[{self.get_entry_type_display()}] {self.title}"
