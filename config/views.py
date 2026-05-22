from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.http import require_POST

from articles.models import Article
from monitoring.tracker import get_client_ip, hash_ip
from presence.models import MaintenanceNote
from recipes.models import Recipe


def _site_base_url() -> str:
    site_domain = str(settings.SITE_DOMAIN).strip().rstrip("/")
    if site_domain.startswith(("http://", "https://")):
        return site_domain
    return f"{settings.SITE_SCHEME}://{site_domain}"


def _absolute_url(path: str) -> str:
    return f"{_site_base_url()}{path}"


def robots_txt(_request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /messages/",
        "Disallow: /presence/",
        "Disallow: /recipes/moderation/",
        "Disallow: /monitoring/",
        f"Sitemap: {_absolute_url(reverse('sitemap_xml'))}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def sitemap_xml(_request):
    entries = [
        {"loc": _absolute_url(reverse("home")), "changefreq": "weekly", "priority": "1.0"},
        {"loc": _absolute_url(reverse("recipes:recipe_list")), "changefreq": "daily", "priority": "0.9"},
        {"loc": _absolute_url(reverse("articles:article_list")), "changefreq": "daily", "priority": "0.8"},
        {"loc": _absolute_url(reverse("about")), "changefreq": "monthly", "priority": "0.5"},
        {"loc": _absolute_url(reverse("privacy")), "changefreq": "yearly", "priority": "0.3"},
        {"loc": _absolute_url(reverse("messaging:contact")), "changefreq": "monthly", "priority": "0.4"},
    ]

    recipes = (
        Recipe.objects.filter(status=Recipe.Status.APPROVED, is_deleted=False)
        .only("slug", "updated_at")
        .order_by("slug")
    )
    for recipe in recipes:
        entries.append(
            {
                "loc": _absolute_url(recipe.get_absolute_url()),
                "lastmod": recipe.updated_at.date().isoformat(),
                "changefreq": "monthly",
                "priority": "0.7",
            }
        )

    articles = (
        Article.objects.filter(status=Article.Status.APPROVED, is_deleted=False)
        .only("slug", "published")
        .order_by("slug")
    )
    for article in articles:
        entries.append(
            {
                "loc": _absolute_url(article.get_absolute_url()),
                "lastmod": article.published.isoformat(),
                "changefreq": "monthly",
                "priority": "0.6",
            }
        )

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for entry in entries:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{escape(entry['loc'])}</loc>")
        if entry.get("lastmod"):
            xml_lines.append(f"    <lastmod>{entry['lastmod']}</lastmod>")
        xml_lines.append(f"    <changefreq>{entry['changefreq']}</changefreq>")
        xml_lines.append(f"    <priority>{entry['priority']}</priority>")
        xml_lines.append("  </url>")
    xml_lines.append("</urlset>")

    return HttpResponse("\n".join(xml_lines), content_type="application/xml; charset=utf-8")


@require_POST
def maintenance_login(request):
    """Staff-only login from the maintenance door page."""
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    error = ""
    user = authenticate(request, username=username, password=password)
    if user is not None and (user.is_superuser or user.is_staff):
        login(request, user)
        return redirect(reverse("recipes:moderation_panel"))
    else:
        error = "Sorry, we are undergoing maintenance. Please come back later."
    from config.maintenance import read_maintenance_flag

    flag = read_maintenance_flag()
    maintenance_until = ""
    if flag:
        maintenance_until = flag.get("until", "")
    if not maintenance_until:
        maintenance_until = getattr(settings, "MAINTENANCE_UNTIL", "")
    retry_after = getattr(settings, "MAINTENANCE_RETRY_AFTER_SECONDS", 10800)
    return render(
        request,
        "maintenance.html",
        {
            "maintenance_until": maintenance_until,
            "retry_after_seconds": retry_after,
            "door_notes": [],
            "login_error": error,
        },
        status=503,
    )


@require_POST
def maintenance_toggle(request):
    from accounts.views import can_grant_bearseeker_privileges
    from django.http import HttpResponseForbidden

    if not can_grant_bearseeker_privileges(request.user):
        return HttpResponseForbidden()

    from datetime import datetime
    from datetime import timezone as dt_timezone

    from config.maintenance import clear_maintenance_flag, set_maintenance_flag

    action = request.POST.get("action", "")
    if action == "activate":
        try:
            hours = max(0, min(72, int(request.POST.get("hours") or 0)))
            minutes = max(0, min(59, int(request.POST.get("minutes") or 0)))
        except (ValueError, TypeError):
            hours, minutes = 1, 0
        total_minutes = hours * 60 + minutes
        if total_minutes < 1:
            total_minutes = 60
        until_dt = datetime.now(dt_timezone.utc) + timedelta(minutes=total_minutes)
        set_maintenance_flag(until_dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
    elif action == "deactivate":
        clear_maintenance_flag()

    return redirect(reverse("recipes:moderation_panel"))


@require_POST
def maintenance_note_create(request):
    from config.maintenance import read_maintenance_flag

    env_active = getattr(settings, "MAINTENANCE_MODE", False)
    flag = read_maintenance_flag()
    flag_active = flag is not None and flag.get("active", False)
    if not env_active and not flag_active:
        return redirect("home")

    if request.POST.get("website"):
        return redirect("/#maintenance-door")

    display_name = request.POST.get("display_name", "").strip()[:40]
    message = request.POST.get("message", "").strip()[:240]
    if not message:
        return redirect("/#maintenance-door")

    parent = None
    parent_id = request.POST.get("parent_id", "").strip()
    if parent_id.isdigit():
        try:
            parent = MaintenanceNote.objects.get(id=parent_id, is_visible=True)
            if parent.parent_id:
                parent = parent.parent
        except MaintenanceNote.DoesNotExist:
            parent = None

    ip_hash = hash_ip(get_client_ip(request))
    recent_cutoff = timezone.now() - timedelta(minutes=5)
    if ip_hash and MaintenanceNote.objects.filter(ip_hash=ip_hash, created_at__gte=recent_cutoff).count() >= 5:
        return redirect("/#maintenance-door")

    MaintenanceNote.objects.create(
        display_name=display_name,
        message=message,
        parent=parent,
        ip_hash=ip_hash,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:180],
    )
    return redirect("/#maintenance-door")
