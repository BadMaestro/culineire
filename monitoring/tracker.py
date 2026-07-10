from __future__ import annotations

import hashlib
import hmac
from urllib.parse import unquote

from django.conf import settings
from django.db import DatabaseError

# ── Single authoritative lists — import from here, never redefine ────────────

# Bot user-agent markers (middleware + views)
BOT_UA_MARKERS = (
    "bot", "crawler", "spider", "crawl",
    "censys", "claudebot", "bytespider",
    "semrush", "ahrefs", "mj12bot",
    "bingpreview", "facebookexternalhit", "telegrambot",
    "curl/", "wget/", "python-requests",
    "go-http-client", "httpx", "okhttp",
    "scanner", "zgrab", "masscan", "nuclei",
    "nikto", "sqlmap", "wpscan", "gobuster", "ffuf",
)

# Patterns that trigger a pre-request SecurityEvent in middleware
SUSPICIOUS_TRIGGER_PATTERNS = (
    "<script", "union select", "../../", "etc/passwd",
    "wp-admin", "phpmy", ".env", "xmlrpc",
    "credentials.json", "client_secret", "client_secrets",
    "service-account", "serviceaccount", "firebase", "gcp-",
    "google-credentials", "google-service-account", "sa-key", "sa-private-key",
)

# Paths that elevate severity to "critical" in middleware
CRITICAL_PATH_MARKERS = (
    ".env", ".git", ".sql", ".bak", "etc/passwd",
    "union select", "<script", "../../",
    "credentials.json", "client_secret", "client_secrets",
    "service-account", "serviceaccount", "firebase-adminsdk",
    "google-credentials", "google-service-account",
    "sa-key", "sa-private-key", "stripe-credentials",
)

# Comprehensive path markers used in views for request classification
SUSPICIOUS_PATH_MARKERS = (
    ".env", ".git", ".hg", ".svn", ".sql", ".log", ".bak", ".swp",
    "wp-", "xmlrpc", "phpmy", ".php", "graphql", "swagger",
    "server-status", "server-info", "actuator",
    "bitbucket-pipelines.yml", "amplify.yml", "serverless.yml",
    "serverless.yaml", "dockerfile", "jenkinsfile",
    "composer.json", "package.json",
    "vite.config", "nuxt.config", "next.config", "webpack.config",
    "firebase-debug", "database", "backup", "dump",
    "credentials.json", "client_secret", "client_secrets",
    "service-account", "serviceaccount", "firebase", "gcp-",
    "google-credentials", "google-service-account", "sa-key", "sa-private-key",
    "/logs/", "/var/log/", "/storage/logs/",
    "/%22/", '/"/', "/https:/",
    ".cgi", "docker", "/.well-known/stripe",
    "/iam",
)


def normalized_path_variants(path: str) -> tuple[str, ...]:
    """Return raw and URL-decoded lowercase variants for scanner matching."""
    raw = (path or "").lower()
    variants = [raw]
    decoded = raw
    for _ in range(2):
        next_decoded = unquote(decoded).lower()
        if next_decoded == decoded:
            break
        variants.append(next_decoded)
        decoded = next_decoded
    return tuple(dict.fromkeys(variants))


def path_contains_marker(path: str, markers: tuple[str, ...]) -> bool:
    variants = normalized_path_variants(path)
    return any(marker in variant for variant in variants for marker in markers)


def get_client_ip(request) -> str:
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def hash_ip(ip: str) -> str:
    if not ip:
        return ""
    if not getattr(settings, "MONITORING_ANONYMIZE_IP", True):
        return ip
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, ip.encode("utf-8"), hashlib.sha256).hexdigest()


def track_event(
        request,
        event_type,
        object_type="",
        object_id=None,
        object_title="",
        metadata=None,
):
    if not getattr(settings, "MONITORING_ENABLED", True):
        return
    try:
        from monitoring.models import UserActivity

        user = request.user if hasattr(request, "user") and request.user.is_authenticated else None
        session_key = ""
        if hasattr(request, "session") and request.session.session_key:
            session_key = request.session.session_key

        UserActivity.objects.create(
            user=user,
            session_key=session_key,
            event_type=event_type,
            object_type=object_type,
            object_id=object_id,
            object_title=object_title[:255] if object_title else "",
            ip_hash=hash_ip(get_client_ip(request)),
            path=request.path[:500],
            metadata=metadata or {},
        )
    except (AttributeError, DatabaseError, ImportError):
        pass


def failed_login_severity(ip_hash: str) -> str:
    """Return severity for a failed login based on recent attempts from same IP."""
    if not ip_hash:
        return "medium"
    try:
        from django.utils import timezone
        from monitoring.models import SecurityEvent
        cutoff = timezone.now() - timezone.timedelta(hours=1)
        count = SecurityEvent.objects.filter(
            event_type="failed_login",
            ip_hash=ip_hash,
            created_at__gte=cutoff,
        ).count()
        if count >= 5:
            return "critical"
        if count >= 2:
            return "high"
    except Exception:
        pass
    return "medium"


def record_security_event(request, event_type: str, severity: str | None = None) -> None:
    """Write a SecurityEvent row. severity=None means auto-compute for failed_login."""
    if not getattr(settings, "MONITORING_ENABLED", True):
        return
    try:
        from monitoring.models import SecurityEvent
        ip_hash = hash_ip(get_client_ip(request))
        if severity is None:
            severity = (
                failed_login_severity(ip_hash)
                if event_type == "failed_login"
                else "medium"
            )
        user = request.user if hasattr(request, "user") and request.user.is_authenticated else None
        SecurityEvent.objects.create(
            event_type=event_type,
            severity=severity,
            user=user,
            ip_hash=ip_hash,
            path=request.path[:500],
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )
    except (AttributeError, DatabaseError, ImportError):
        pass
