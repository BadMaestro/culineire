from __future__ import annotations

import logging

from django.conf import settings
from django.db import DatabaseError
from django.http import HttpResponseNotFound
from django.middleware.common import CommonMiddleware

logger = logging.getLogger(__name__)

from .tracker import (
    BOT_UA_MARKERS, SUSPICIOUS_TRIGGER_PATTERNS, CRITICAL_PATH_MARKERS,
    get_client_ip, hash_ip, path_contains_marker,
)

_DEFAULT_EXCLUDED = (
    "/static/", "/media/", "/admin/jsi18n/",
    "/favicon.ico", "/robots.txt",
)

def _is_bot_ua(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    return any(m in ua for m in BOT_UA_MARKERS)


def _suspicious_severity(path: str) -> str:
    if path_contains_marker(path, CRITICAL_PATH_MARKERS):
        return "critical"
    return "medium"


def _404_severity(user_agent: str, path: str) -> str:
    if _is_bot_ua(user_agent):
        return "medium"
    return "low"


def _is_append_slash_redirect_candidate(request) -> bool:
    if not getattr(settings, "APPEND_SLASH", True):
        return False
    if request.path_info.endswith("/"):
        return False
    return CommonMiddleware(lambda _request: None).should_redirect_with_slash(request)


_INTERNAL_MARK_TTL = 7 * 24 * 3600  # staff machines stay excluded for a week per sighting


class MonitoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        excluded = getattr(settings, "MONITORING_EXCLUDED_PATH_PREFIXES", _DEFAULT_EXCLUDED)
        self._excluded = tuple(excluded)
        # Internal traffic (the team's own machines and the server itself) must
        # not pollute visitor statistics. Two mechanisms:
        # 1. MONITORING_INTERNAL_IPS setting — fixed addresses (e.g. the
        #    production host, whose own curls come back via the proxy).
        # 2. Auto-learned: any ip_hash seen with an authenticated staff user is
        #    remembered in cache, so anonymous hits from the same machine
        #    (manifest.json fetches, diagnostic curls) are excluded too.
        self._internal_hashes = frozenset(
            hash_ip(ip.strip())
            for ip in getattr(settings, "MONITORING_INTERNAL_IPS", ())
            if ip.strip()
        )

    def _is_internal(self, ip_hash: str, user) -> bool:
        """Whether this request should be excluded from the public stats.

        Every cache call here is guarded, and that is not defensive padding.
        This middleware runs on EVERY request, so an unreachable cache backend
        raised from this method returns 500 for the entire site, not for one
        page. It happened on 2026-07-22: a single .djcache file left owned by
        root (written by a diagnostic run as the wrong user) made the web worker,
        which runs as deploy, unable to write, and pages began failing.

        Failing to remember that an IP is internal only costs a slightly noisier
        statistics table. Failing to serve the site costs the site. The trade is
        not close.
        """
        if ip_hash in self._internal_hashes:
            return True
        from django.core.cache import cache
        cache_key = f"monitoring:internal_ip:{ip_hash}"
        if user is not None and user.is_staff:
            try:
                cache.set(cache_key, True, _INTERNAL_MARK_TTL)
            except Exception:  # noqa: BLE001 - a broken cache must not break the site
                pass
            return True
        try:
            return bool(cache.get(cache_key))
        except Exception:  # noqa: BLE001
            return False

    def __call__(self, request):
        path = request.path

        if not getattr(settings, "MONITORING_ENABLED", True):
            return self.get_response(request)

        if path.startswith(self._excluded):
            return self.get_response(request)

        if "CulinEire-HealthCheck" in (request.META.get("HTTP_USER_AGENT") or ""):
            return self.get_response(request)

        # Flag suspicious paths before even processing the request.
        is_suspicious = path_contains_marker(path, SUSPICIOUS_TRIGGER_PATTERNS)
        if is_suspicious:
            self._record_security(request, "suspicious_request")
            if getattr(settings, "MONITORING_BLOCK_SUSPICIOUS_PROBES", True):
                return HttpResponseNotFound()

        # Force session creation for real browsers so anonymous mobile visitors
        # get a session_key and are counted correctly in visitor stats.
        # Bots don't persist cookies between requests, so this only sticks for real browsers.
        ua = request.META.get("HTTP_USER_AGENT", "")
        ua_lower = ua.lower()
        if (
            hasattr(request, "session")
            and not request.session.session_key
            and not any(m in ua_lower for m in BOT_UA_MARKERS)
        ):
            request.session["_v"] = 1

        response = self.get_response(request)

        try:
            self._record_response(request, response, is_suspicious)
        except (AttributeError, DatabaseError):
            logger.debug("MonitoringMiddleware: could not record response for %s", request.path, exc_info=True)

        return response

    def _record_response(self, request, response, is_suspicious):
        if is_suspicious:
            return

        from monitoring.models import PageView, SecurityEvent

        status = response.status_code
        ip_hash = hash_ip(get_client_ip(request))
        user = request.user if hasattr(request, "user") and request.user.is_authenticated else None

        # Team/server traffic stays out of the statistics entirely (page views
        # and routine 403/404 noise). Genuinely suspicious probes are still
        # recorded above regardless of source.
        if self._is_internal(ip_hash, user):
            return
        session_key = ""
        if hasattr(request, "session") and request.session.session_key:
            session_key = request.session.session_key
        path = request.path[:500]
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:200]
        referrer = request.META.get("HTTP_REFERER", "")[:500]

        if status == 404:
            if _is_append_slash_redirect_candidate(request):
                return
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
                is_bot=_is_bot_ua(user_agent),
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
            logger.debug("MonitoringMiddleware: could not record security event for %s", request.path, exc_info=True)
