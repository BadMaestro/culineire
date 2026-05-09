from __future__ import annotations

from django.conf import settings
from django.db import DatabaseError

from .tracker import get_client_ip, hash_ip

_SUSPICIOUS_PATTERNS = (
    "<script", "union select", "../../", "etc/passwd",
    "wp-admin", "phpmy", ".env", "xmlrpc",
)

_DEFAULT_EXCLUDED = (
    "/static/", "/media/", "/admin/jsi18n/",
    "/favicon.ico", "/robots.txt",
)


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

        # Flag suspicious paths before even processing the request.
        path_lower = path.lower()
        is_suspicious = any(p in path_lower for p in _SUSPICIOUS_PATTERNS)
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
                user=user,
                ip_hash=ip_hash,
                path=path,
                user_agent=user_agent,
            )
            return

        if status == 403:
            SecurityEvent.objects.create(
                event_type=SecurityEvent.EventType.FORBIDDEN,
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
            SecurityEvent.objects.create(
                event_type=event_type,
                user=user,
                ip_hash=hash_ip(get_client_ip(request)),
                path=request.path[:500],
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
            )
        except (AttributeError, DatabaseError):
            pass
