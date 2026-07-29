from __future__ import annotations

from django.db import connection, models, transaction
from django.utils import timezone

# Postgres channel every recipient's waiter LISTENs on. The payload is the
# recipient agent_id, so one channel serves the whole team and a waiter can
# ignore notifications addressed to someone else.
COWORK_INBOX_CHANNEL = "cowork_inbox"


def notify_inbox(agent_id: str) -> None:
    """Fire a Postgres NOTIFY so a waiting recipient wakes the instant a message
    lands, instead of discovering it on the next timed poll. No-op off Postgres
    (local sqlite dev) and never fatal — delivery is the message row; the NOTIFY
    is only the doorbell."""
    if connection.vendor != "postgresql":
        return
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT pg_notify(%s, %s)", [COWORK_INBOX_CHANNEL, agent_id])
    except Exception:
        # A failed doorbell must never lose a delivered message; the waiter's
        # periodic re-check still finds it.
        pass


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

    # These JSON fields are lists by contract, and the dashboard iterates them.
    _LIST_FIELDS = ("task_files_touched", "key_facts", "decisions_made", "blockers")

    def __str__(self):
        return self.label or self.agent_id

    def save(self, *args, **kwargs):
        # An agent that assigns a plain string to one of these fields directly
        # (bypassing coworking_update, which appends to a list) would make the
        # dashboard render it one character per <li>. Coerce a stray string or
        # None into a list here so bad input can never break the board again.
        for field in self._LIST_FIELDS:
            value = getattr(self, field)
            if isinstance(value, str):
                setattr(self, field, [value] if value.strip() else [])
            elif value is None:
                setattr(self, field, [])
        super().save(*args, **kwargs)

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


class CoworkingMessage(models.Model):
    """A directed message from one agent to another.

    Unlike CoworkingLogEntry (a public activity log), this is addressed to a
    specific agent and carries a read flag, so an agent can poll its own inbox
    for genuinely new, unhandled messages instead of grepping the shared log.
    """

    from_agent = models.ForeignKey(
        CoworkingAgent, on_delete=models.CASCADE, related_name="sent_messages"
    )
    to_agent = models.ForeignKey(
        CoworkingAgent, on_delete=models.CASCADE, related_name="received_messages"
    )
    subject = models.CharField(max_length=1000, blank=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["to_agent", "read_at"]),
        ]

    def __str__(self):
        state = "read" if self.read_at else "unread"
        return f"{self.from_agent_id}->{self.to_agent_id} [{state}]: {self.subject or self.body[:40]}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])

    @classmethod
    def send(cls, *, from_agent, to_agent, body: str, subject: str = "") -> "CoworkingMessage":
        """Send a message. Agents may be CoworkingAgent instances or agent_id strings."""
        if isinstance(from_agent, str):
            from_agent, _ = CoworkingAgent.objects.get_or_create(
                agent_id=from_agent, defaults={"label": from_agent.title()}
            )
        if isinstance(to_agent, str):
            to_agent, _ = CoworkingAgent.objects.get_or_create(
                agent_id=to_agent, defaults={"label": to_agent.title()}
            )
        msg = cls.objects.create(
            from_agent=from_agent, to_agent=to_agent, subject=subject, body=body
        )
        # Ring the recipient's doorbell only after the row is durably committed,
        # so the waiter that wakes always finds the message it was told about.
        recipient_id = msg.to_agent_id
        transaction.on_commit(lambda: notify_inbox(recipient_id))
        return msg

    @classmethod
    def unread_for(cls, agent_id: str):
        """Unread messages addressed to agent_id, oldest first."""
        return (
            cls.objects.filter(to_agent_id=agent_id, read_at__isnull=True)
            .select_related("from_agent")
            .order_by("created_at")
        )


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
