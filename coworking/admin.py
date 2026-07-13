from django.contrib import admin

from .models import (
    CoworkingAgent,
    CoworkingLogEntry,
    CoworkingMessage,
    CoworkingSharedMemory,
)


class CoworkingLogEntryInline(admin.TabularInline):
    model = CoworkingLogEntry
    extra = 0
    readonly_fields = ["ts"]
    ordering = ["-ts"]


@admin.register(CoworkingAgent)
class CoworkingAgentAdmin(admin.ModelAdmin):
    list_display = ["agent_id", "label", "status", "last_seen", "task_title"]
    inlines = [CoworkingLogEntryInline]


@admin.register(CoworkingMessage)
class CoworkingMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "from_agent", "to_agent", "subject", "created_at", "read_at"]
    list_filter = ["to_agent", "from_agent", "read_at"]
    search_fields = ["subject", "body"]
    readonly_fields = ["created_at"]


@admin.register(CoworkingSharedMemory)
class CoworkingSharedMemoryAdmin(admin.ModelAdmin):
    list_display = ["updated_at"]
