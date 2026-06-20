from __future__ import annotations

from django.db import models
from django.utils import timezone


class CoworkingAgent(models.Model):
    """One AI agent (e.g. "Bolt", "GreenBear") working on this codebase.

    The production database is the shared state between agents on
    different machines/accounts — no git/file sync needed, every agent
    talks to the same live database via management commands.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        IDLE = "idle", "Idle"
        BLOCKED = "blocked", "Blocked"

    agent_id = models.SlugField(primary_key=True, max_length=40)
    label = models.CharField(max_length=120)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.IDLE)
    last_seen = models.DateTimeField(null=True, blank=True)

    task_title = models.CharField(max_length=255, blank=True)
    task_description = models.TextField(blank=True)
    task_branch = models.CharField(max_length=120, blank=True)
    task_files_touched = models.JSONField(default=list, blank=True)
    task_next_step = models.TextField(blank=True)
    task_started_at = models.DateTimeField(null=True, blank=True)

    active_prompt = models.TextField(blank=True)

    key_facts = models.JSONField(default=list, blank=True)
    decisions_made = models.JSONField(default=list, blank=True)
    blockers = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["agent_id"]

    def __str__(self):
        return self.label or self.agent_id

    def touch(self):
        self.last_seen = timezone.now()


class CoworkingLogEntry(models.Model):
    class Result(models.TextChoices):
        OK = "ok", "OK"
        BLOCKED = "blocked", "Blocked"
        PENDING = "pending", "Pending"

    agent = models.ForeignKey(CoworkingAgent, on_delete=models.CASCADE, related_name="log_entries")
    ts = models.DateTimeField(auto_now_add=True)
    action = models.TextField()
    result = models.CharField(max_length=16, choices=Result.choices, default=Result.OK)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-ts"]

    def __str__(self):
        return f"{self.agent_id} @ {self.ts}: {self.action[:50]}"


class CoworkingSharedMemory(models.Model):
    """Singleton row holding cross-agent project memory."""

    project_memory = models.JSONField(default=list, blank=True)
    open_questions = models.JSONField(default=list, blank=True)
    completed_today = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Coworking shared memory"
        verbose_name_plural = "Coworking shared memory"

    @classmethod
    def load(cls) -> "CoworkingSharedMemory":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
