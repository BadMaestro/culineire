from __future__ import annotations

from django.conf import settings
from django.db import DatabaseError, OperationalError, ProgrammingError
from django.db.models import Prefetch
from django.shortcuts import render


class MaintenanceModeMiddleware:
    allowed_prefixes = (
        "/static/",
        "/media/",
    )
    allowed_paths = (
        "/favicon.ico",
        "/favicon.png",
        "/apple-touch-icon.png",
        "/robots.txt",
        "/sitemap.xml",
        "/maintenance/notes/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "MAINTENANCE_MODE", False):
            return self.get_response(request)

        path = request.path_info or request.path
        if path in self.allowed_paths or path.startswith(self.allowed_prefixes):
            return self.get_response(request)

        retry_after = getattr(settings, "MAINTENANCE_RETRY_AFTER_SECONDS", 10800)
        response = render(
            request,
            "maintenance.html",
            {
                "maintenance_until": getattr(settings, "MAINTENANCE_UNTIL", ""),
                "retry_after_seconds": retry_after,
                "door_notes": self._door_notes(),
            },
            status=503,
        )
        response["Retry-After"] = str(retry_after)
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        return response

    def _door_notes(self):
        try:
            from presence.models import MaintenanceNote

            visible_replies = MaintenanceNote.objects.filter(is_visible=True).order_by("created_at")
            return list(
                MaintenanceNote.objects.filter(is_visible=True, parent__isnull=True)
                .prefetch_related(Prefetch("replies", queryset=visible_replies, to_attr="visible_replies"))
                .order_by("-created_at")[:12]
            )
        except (DatabaseError, OperationalError, ProgrammingError, ImportError):
            return []
