from __future__ import annotations

from django.db import models


class ContentReport(models.Model):
    class ReportType(models.TextChoices):
        COPYRIGHT = "copyright", "Copyright infringement"
        WATERMARK = "watermark", "Watermarked or unlicensed image"
        INACCURATE_CREDIT = "inaccurate_credit", "Inaccurate or missing credit"
        STOLEN_RECIPE = "stolen_recipe", "Stolen or uncredited recipe"
        OTHER = "other", "Other"

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
    reporter_name = models.CharField("Your name", max_length=100)
    reporter_email = models.EmailField("Your email")
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
        return f"{self.get_report_type_display()} from {self.reporter_name} ({self.created_at:%Y-%m-%d})"
