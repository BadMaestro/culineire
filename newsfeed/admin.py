from django.contrib import admin

from .models import NewsFeedEntry


@admin.register(NewsFeedEntry)
class NewsFeedEntryAdmin(admin.ModelAdmin):
    list_display = ("title", "entry_type", "is_public", "is_auto", "published_at", "version")
    list_filter = ("entry_type", "is_public", "is_auto")
    list_editable = ("is_public",)
    ordering = ("-published_at",)
    readonly_fields = ("is_auto", "event_key", "created_by")
    search_fields = ("title", "message", "version")
    date_hierarchy = "published_at"

    fieldsets = (
        (None, {
            "fields": ("entry_type", "title", "message", "url", "version", "published_at", "is_public"),
        }),
        ("System", {
            "classes": ("collapse",),
            "fields": ("is_auto", "event_key", "created_by"),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_auto:
            return self.readonly_fields + ("entry_type", "title", "url")
        return self.readonly_fields
