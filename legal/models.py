from __future__ import annotations

from django.conf import settings
from django.db import models


class ContentReport(models.Model):
    class ReportType(models.TextChoices):
        COPYRIGHT = "copyright", "Copyright infringement"
        WATERMARK = "watermark", "Watermarked or unlicensed image"
        INACCURATE_CREDIT = "inaccurate_credit", "Inaccurate or missing credit"
        STOLEN_RECIPE = "stolen_recipe", "Stolen or uncredited recipe"
        PRIVACY_DATA = "privacy_data", "Privacy or personal data concern"
        IMPERSONATION = "impersonation", "Impersonation or fake identity"
        DEFAMATION = "defamation", "Defamatory or harmful content"
        FOOD_SAFETY = "food_safety", "Food safety or allergen concern"
        SPAM = "spam", "Spam or promotional abuse"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        UNDER_REVIEW = "under_review", "Under review"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    recipe = models.ForeignKey(
        "recipes.Recipe",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_reports",
        verbose_name="Reported recipe",
    )
    article = models.ForeignKey(
        "articles.Article",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_reports",
        verbose_name="Reported article",
    )
    reporter_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_reports",
        verbose_name="Reporter",
    )
    linked_message = models.ForeignKey(
        "messaging.Message",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Linked message",
    )
    reporter_name = models.CharField("Your name", max_length=100)
    reporter_email = models.EmailField("Your email")
    organisation = models.CharField(
        "Organisation (optional)",
        max_length=200,
        blank=True,
    )
    evidence_url = models.CharField(
        "Link to original source or evidence (optional)",
        max_length=500,
        blank=True,
    )
    good_faith_confirmed = models.BooleanField(
        "Good faith declaration",
        default=False,
        help_text="I confirm this report is made in good faith and the information is accurate to the best of my knowledge.",
    )
    status = models.CharField(
        "Status",
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    updated_at = models.DateTimeField(auto_now=True)
    handled_at = models.DateTimeField("Handled at", null=True, blank=True)
    internal_notes = models.TextField("Internal notes", blank=True)
    report_type = models.CharField(
        "Type of issue",
        max_length=30,
        choices=ReportType.choices,
        default=ReportType.COPYRIGHT,
    )
    reported_url = models.CharField(
        "URL of the content in question",
        max_length=500,
        blank=True,
    )
    description = models.TextField(
        "Description",
        max_length=2000,
        help_text="Please describe the issue clearly. Include the original source if applicable.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField("Resolved", default=False)
    resolved_note = models.CharField("Resolution note", max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Content report"
        verbose_name_plural = "Content reports"

    def __str__(self) -> str:
        name = self.reporter_name or (self.reporter_user.username if self.reporter_user else "unknown")
        return f"{self.get_report_type_display()} from {name} ({self.created_at:%Y-%m-%d})"
