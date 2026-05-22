from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError, OperationalError, ProgrammingError
from django.db.models import Prefetch
from django.shortcuts import render


def _get_flag_path() -> Path:
    cache_dir = getattr(settings, "CACHE_DIR", None)
    if cache_dir is None:
        cache_dir = Path(settings.BASE_DIR) / "cache"
    return Path(cache_dir) / "maintenance_flag.json"


def read_maintenance_flag() -> dict | None:
    try:
        data = json.loads(_get_flag_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def set_maintenance_flag(until_iso: str) -> None:
    flag_path = _get_flag_path()
    data = json.dumps({"active": True, "until": until_iso}, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=str(flag_path.parent), suffix=".tmp")
    try:
        os.write(fd, data.encode("utf-8"))
        os.close(fd)
        os.replace(tmp, flag_path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def clear_maintenance_flag() -> None:
    try:
        _get_flag_path().unlink()
    except FileNotFoundError:
        pass


def _is_privileged_user(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    owner_slug = getattr(settings, "OWNER_SLUG", "greenbear")
    try:
        return user.recipe_author_profile.slug == owner_slug
    except Exception:
        return False


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
        "/maintenance/toggle/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        env_active = getattr(settings, "MAINTENANCE_MODE", False)
        flag = read_maintenance_flag()
        flag_active = flag is not None and flag.get("active", False)

        if not env_active and not flag_active:
            return self.get_response(request)

        if _is_privileged_user(request.user):
            return self.get_response(request)

        path = request.path_info or request.path
        if path in self.allowed_paths or path.startswith(self.allowed_prefixes):
            return self.get_response(request)
        admin_url = getattr(settings, "ADMIN_URL_PREFIX", "cave19850324")
        if path.startswith(f"/{admin_url}/"):
            return self.get_response(request)

        maintenance_until = ""
        if flag_active:
            maintenance_until = flag.get("until", "")
        if not maintenance_until:
            maintenance_until = getattr(settings, "MAINTENANCE_UNTIL", "")

        retry_after = getattr(settings, "MAINTENANCE_RETRY_AFTER_SECONDS", 10800)
        response = render(
            request,
            "maintenance.html",
            {
                "maintenance_until": maintenance_until,
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
