from django.contrib import admin

from .models import CoworkingAgent, CoworkingLogEntry, CoworkingSharedMemory


class CoworkingLogEntryInline(admin.TabularInline):
    model = CoworkingLogEntry
    extra = 0
    readonly_fields = ["ts"]
    ordering = ["-ts"]


@admin.register(CoworkingAgent)
class CoworkingAgentAdmin(admin.ModelAdmin):
    list_display = ["agent_id", "label", "status", "last_seen", "task_title"]
    inlines = [CoworkingLogEntryInline]


@admin.register(CoworkingSharedMemory)
class CoworkingSharedMemoryAdmin(admin.ModelAdmin):
    list_display = ["updated_at"]
