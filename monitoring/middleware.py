from __future__ import annotations

from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone

from .tracker import (
    BOT_UA_MARKERS, SUSPICIOUS_TRIGGER_PATTERNS, CRITICAL_PATH_MARKERS,
    get_client_ip, hash_ip, failed_login_severity,
)

_DEFAULT_EXCLUDED = (
    "/static/", "/media/", "/admin/jsi18n/",
    "/favicon.ico", "/robots.txt",
)

def _is_bot_ua(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    return any(m in ua for m in BOT_UA_MARKERS)


def _suspicious_severity(path: str) -> str:
    p = (path or "").lower()
    if any(m in p for m in CRITICAL_PATH_MARKERS):
        return "critical"
    return "medium"


def _404_severity(user_agent: str, path: str) -> str:
    if _is_bot_ua(user_agent):
        return "medium"
    return "low"


class MonitoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        excluded = getattr(settings, "MONITORING_EXCLUDED_PATH_PREFIXES", _DEFAULT_EXCLUDED)
        self._excluded = tuple(excluded)

    def __call__(self, request):
        path = request.path

        if not getattr(settings, "MONITORING_ENABLED", True):
            return self.get_response(request)

        if path.startswith(self._excluded):
            return self.get_response(request)

        if "CulinEire-HealthCheck" in (request.META.get("HTTP_USER_AGENT") or ""):
            return self.get_response(request)

        # Flag suspicious paths before even processing the request.
        path_lower = path.lower()
        is_suspicious = any(p in path_lower for p in SUSPICIOUS_TRIGGER_PATTERNS)
        if is_suspicious:
            self._record_security(request, "suspicious_request")

        response = self.get_response(request)

        try:
            self._record_response(request, response, is_suspicious)
        except (AttributeError, DatabaseError):
            pass

        return response

    @staticmethod
    def _record_response(request, response, is_suspicious):
        if is_suspicious:
            return

        from monitoring.models import PageView, SecurityEvent

        status = response.status_code
        ip_hash = hash_ip(get_client_ip(request))
        user = request.user if hasattr(request, "user") and request.user.is_authenticated else None
        session_key = ""
        if hasattr(request, "session") and request.session.session_key:
            session_key = request.session.session_key
        path = request.path[:500]
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:200]
        referrer = request.META.get("HTTP_REFERER", "")[:500]

        if status == 404:
            SecurityEvent.objects.create(
                event_type=SecurityEvent.EventType.NOT_FOUND,
                severity=_404_severity(user_agent, path),
                user=user,
                ip_hash=ip_hash,
                path=path,
                user_agent=user_agent,
            )
            return

        if status == 403:
            SecurityEvent.objects.create(
                event_type=SecurityEvent.EventType.FORBIDDEN,
                severity="medium",
                user=user,
                ip_hash=ip_hash,
                path=path,
                user_agent=user_agent,
            )
            return

        # Only record successful page views; skip admin internals.
        if status < 400 and not path.startswith("/admin/"):
            PageView.objects.create(
                path=path,
                referrer=referrer,
                user=user,
                session_key=session_key,
                ip_hash=ip_hash,
                user_agent=user_agent,
                status_code=status,
            )

    @staticmethod
    def _record_security(request, event_type):
        try:
            from monitoring.models import SecurityEvent

            user = request.user if hasattr(request, "user") and request.user.is_authenticated else None
            ip_hash = hash_ip(get_client_ip(request))
            path = request.path[:500]
            user_agent = request.META.get("HTTP_USER_AGENT", "")[:300]
            severity = _suspicious_severity(path)
            SecurityEvent.objects.create(
                event_type=event_type,
                severity=severity,
                user=user,
                ip_hash=ip_hash,
                path=path,
                user_agent=user_agent,
            )
        except (AttributeError, DatabaseError):
            pass
