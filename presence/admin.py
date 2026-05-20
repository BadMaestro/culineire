from django.contrib import admin

from .models import MaintenanceNote, PresenceEvent


@admin.register(PresenceEvent)
class PresenceEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "triggered_by", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("triggered_by__username", "triggered_by__email")
    readonly_fields = ("created_at",)


@admin.register(MaintenanceNote)
class MaintenanceNoteAdmin(admin.ModelAdmin):
    list_display = ("name_or_guest", "short_message", "parent", "is_visible", "created_at")
    list_filter = ("is_visible", "created_at")
    search_fields = ("display_name", "message", "ip_hash", "user_agent")
    readonly_fields = ("ip_hash", "user_agent", "created_at")
    actions = ("hide_notes", "show_notes")

    @admin.display(description="Message")
    def short_message(self, obj):
        return obj.message[:80]

    @admin.action(description="Hide selected notes")
    def hide_notes(self, request, queryset):
        queryset.update(is_visible=False)

    @admin.action(description="Show selected notes")
    def show_notes(self, request, queryset):
        queryset.update(is_visible=True)
