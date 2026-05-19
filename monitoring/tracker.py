from __future__ import annotations

import hashlib
import hmac

from django.conf import settings
from django.db import DatabaseError

# Single authoritative list of bot user-agent markers.
# Imported by both middleware.py and views.py — edit here only.
BOT_UA_MARKERS = (
    "bot", "crawler", "spider", "crawl",
    "censys", "claudebot", "bytespider",
    "semrush", "ahrefs", "mj12bot",
    "bingpreview", "facebookexternalhit", "telegrambot",
    "curl/", "wget/", "python-requests",
    "go-http-client", "httpx", "okhttp",
)


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
