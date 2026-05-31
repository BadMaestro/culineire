from django.contrib import admin
from django.utils import timezone

from .models import ContentReport


@admin.register(ContentReport)
class ContentReportAdmin(admin.ModelAdmin):
    list_display = (
        "reporter_name",
        "reporter_email",
        "organisation",
        "report_type",
        "status",
        "recipe",
        "article",
        "is_resolved",
        "created_at",
    )
    list_filter = ("report_type", "status", "is_resolved", "created_at")
    list_editable = ("is_resolved", "status")
    search_fields = (
        "reporter_name",
        "reporter_email",
        "organisation",
        "description",
        "reported_url",
        "evidence_url",
        "internal_notes",
    )
    ordering = ("-created_at",)
    readonly_fields = (
        "reporter_name",
        "reporter_email",
        "organisation",
        "report_type",
        "reported_url",
        "evidence_url",
        "description",
        "good_faith_confirmed",
        "created_at",
        "updated_at",
        "recipe",
        "article",
        "reporter_user",
        "linked_message",
    )
    fieldsets = (
        (
            "Reporter",
            {
                "fields": (
                    "reporter_name",
                    "reporter_email",
                    "organisation",
                    "reporter_user",
                    "good_faith_confirmed",
                )
            },
        ),
        (
            "Report",
            {
                "fields": (
                    "report_type",
                    "reported_url",
                    "evidence_url",
                    "recipe",
                    "article",
                    "description",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Resolution",
            {
                "fields": (
                    "status",
                    "is_resolved",
                    "resolved_note",
                    "handled_at",
                    "internal_notes",
                    "linked_message",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        # Auto-set handled_at when status moves to resolved or dismissed
        if change and "status" in form.changed_data:
            if obj.status in (ContentReport.Status.RESOLVED, ContentReport.Status.DISMISSED):
                if not obj.handled_at:
                    obj.handled_at = timezone.now()
            elif obj.status in (ContentReport.Status.OPEN, ContentReport.Status.UNDER_REVIEW):
                obj.handled_at = None
        super().save_model(request, obj, form, change)
