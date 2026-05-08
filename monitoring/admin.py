from django.contrib import admin

from .models import PageView, SecurityEvent, UserActivity


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ("path", "status_code", "user", "session_key", "created_at")
    list_filter = ("status_code", "created_at")
    search_fields = ("path", "referrer", "user__username")
    readonly_fields = ("path", "referrer", "user", "session_key", "ip_hash", "user_agent", "status_code", "created_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ("event_type", "user", "object_type", "object_title", "created_at")
    list_filter = ("event_type", "object_type", "created_at")
    search_fields = ("user__username", "object_title", "path")
    readonly_fields = (
        "user", "session_key", "event_type", "object_type", "object_id",
        "object_title", "ip_hash", "path", "metadata", "created_at",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "user", "path", "ip_hash", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("path", "user__username", "ip_hash")
    readonly_fields = ("event_type", "user", "ip_hash", "path", "user_agent", "metadata", "created_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
