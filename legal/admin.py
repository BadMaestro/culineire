from django.contrib import admin

from .models import ContentReport


@admin.register(ContentReport)
class ContentReportAdmin(admin.ModelAdmin):
    list_display = ("reporter_name", "reporter_email", "report_type", "recipe", "article", "is_resolved", "created_at")
    list_filter = ("report_type", "is_resolved", "created_at")
    list_editable = ("is_resolved",)
    search_fields = ("reporter_name", "reporter_email", "description", "reported_url")
    ordering = ("-created_at",)
    readonly_fields = ("reporter_name", "reporter_email", "report_type", "reported_url", "description", "created_at", "recipe", "article")
    fieldsets = (
        (
            "Report",
            {
                "fields": (
                    "reporter_name",
                    "reporter_email",
                    "report_type",
                    "reported_url",
                    "recipe",
                    "article",
                    "description",
                    "created_at",
                )
            },
        ),
        (
            "Resolution",
            {
                "fields": (
                    "is_resolved",
                    "resolved_note",
                )
            },
        ),
    )
