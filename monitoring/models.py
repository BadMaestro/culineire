from django.conf import settings
from django.db import models


class PageView(models.Model):
    path = models.CharField(max_length=500, db_index=True)
    referrer = models.CharField(max_length=500, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="page_views",
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=200, blank=True)
    status_code = models.PositiveSmallIntegerField(default=200)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Page view"
        verbose_name_plural = "Page views"

    def __str__(self):
        return f"{self.path} [{self.status_code}] @ {self.created_at:%Y-%m-%d %H:%M}"


class UserActivity(models.Model):
    class EventType(models.TextChoices):
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        REGISTER = "register", "Register"
        PROFILE_UPDATE = "profile_update", "Profile Update"
        RECIPE_VIEW = "recipe_view", "Recipe View"
        ARTICLE_VIEW = "article_view", "Article View"
        COMMENT = "comment", "Comment"
        FAILED_LOGIN = "failed_login", "Failed Login"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activities",
    )
    session_key = models.CharField(max_length=40, blank=True)
    event_type = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    object_type = models.CharField(max_length=50, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_title = models.CharField(max_length=255, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    path = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "User activity"
        verbose_name_plural = "User activities"

    def __str__(self):
        user_label = self.user.username if self.user else "anon"
        return f"{self.event_type} — {user_label} @ {self.created_at:%Y-%m-%d %H:%M}"


class SecurityEvent(models.Model):
    class EventType(models.TextChoices):
        FAILED_LOGIN = "failed_login", "Failed Login"
        SUSPICIOUS_REQUEST = "suspicious_request", "Suspicious Request"
        NOT_FOUND = "404", "404 Not Found"
        FORBIDDEN = "403", "403 Forbidden"
        RATE_LIMITED = "rate_limited", "Rate Limited"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    event_type = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.MEDIUM,
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="security_events",
    )
    ip_hash = models.CharField(max_length=64, blank=True)
    path = models.CharField(max_length=500, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Security event"
        verbose_name_plural = "Security events"

    def __str__(self):
        return f"{self.event_type} — {self.path} @ {self.created_at:%Y-%m-%d %H:%M}"
