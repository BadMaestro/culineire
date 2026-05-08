from __future__ import annotations

from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from recipes.views import _is_moderator

from .models import PageView, SecurityEvent, UserActivity

User = get_user_model()


def _require_moderator(request):
    if not _is_moderator(request.user):
        raise Http404


def dashboard(request):
    _require_moderator(request)

    now = timezone.now()
    today = now.date()
    five_min_ago = now - timezone.timedelta(minutes=5)
    seven_days_ago = now - timezone.timedelta(days=7)

    # ── Summary cards ─────────────────────────────────────────────────────────
    online_now = (
        PageView.objects
        .filter(created_at__gte=five_min_ago)
        .exclude(session_key="")
        .values("session_key")
        .distinct()
        .count()
    )

    visitors_today = (
        PageView.objects
        .filter(created_at__date=today)
        .exclude(session_key="")
        .values("session_key")
        .distinct()
        .count()
    )

    pageviews_today = PageView.objects.filter(created_at__date=today).count()

    new_users_today = (
        UserActivity.objects
        .filter(event_type=UserActivity.EventType.REGISTER, created_at__date=today)
        .count()
    )

    active_users_today = (
        UserActivity.objects
        .filter(created_at__date=today)
        .exclude(user=None)
        .values("user")
        .distinct()
        .count()
    )

    # ── Security summary ──────────────────────────────────────────────────────
    count_404_today = SecurityEvent.objects.filter(
        event_type=SecurityEvent.EventType.NOT_FOUND,
        created_at__date=today,
    ).count()

    failed_logins_today = SecurityEvent.objects.filter(
        event_type=SecurityEvent.EventType.FAILED_LOGIN,
        created_at__date=today,
    ).count()

    suspicious_today = SecurityEvent.objects.filter(
        event_type=SecurityEvent.EventType.SUSPICIOUS_REQUEST,
        created_at__date=today,
    ).count()

    # ── Most viewed recipes ───────────────────────────────────────────────────
    top_recipe_rows = (
        UserActivity.objects
        .filter(event_type=UserActivity.EventType.RECIPE_VIEW, object_type="recipe")
        .values("object_id", "object_title")
        .annotate(views=Count("id"))
        .order_by("-views")[:10]
    )
    # Deduplicate by object_id (keep highest-count title)
    seen_recipe_ids: set[int] = set()
    top_recipes = []
    for row in top_recipe_rows:
        if row["object_id"] not in seen_recipe_ids:
            seen_recipe_ids.add(row["object_id"])
            top_recipes.append(row)

    # ── Most viewed articles ──────────────────────────────────────────────────
    top_article_rows = (
        UserActivity.objects
        .filter(event_type=UserActivity.EventType.ARTICLE_VIEW, object_type="article")
        .values("object_id", "object_title")
        .annotate(views=Count("id"))
        .order_by("-views")[:10]
    )
    seen_article_ids: set[int] = set()
    top_articles = []
    for row in top_article_rows:
        if row["object_id"] not in seen_article_ids:
            seen_article_ids.add(row["object_id"])
            top_articles.append(row)

    # ── Top paths (7 days) ────────────────────────────────────────────────────
    top_paths = (
        PageView.objects
        .filter(created_at__gte=seven_days_ago)
        .values("path")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # ── Top referrers (7 days) ────────────────────────────────────────────────
    top_referrers = (
        PageView.objects
        .filter(created_at__gte=seven_days_ago)
        .exclude(referrer="")
        .values("referrer")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # ── Latest activities ─────────────────────────────────────────────────────
    latest_activities = (
        UserActivity.objects
        .select_related("user")
        .order_by("-created_at")[:25]
    )

    # ── Latest security events ────────────────────────────────────────────────
    latest_security = (
        SecurityEvent.objects
        .select_related("user")
        .order_by("-created_at")[:25]
    )

    # ── Hourly pageviews chart (today, 24 buckets) ────────────────────────────
    hourly_views = list(
        PageView.objects
        .filter(created_at__date=today)
        .extra(select={"hour": "strftime('%%H', created_at)"})
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    hourly_map = {row["hour"]: row["count"] for row in hourly_views}
    current_hour = now.hour
    chart_hours = [
        {"hour": f"{h:02d}", "count": hourly_map.get(f"{h:02d}", 0)}
        for h in range(24)
        if h <= current_hour
    ]
    chart_max = max((b["count"] for b in chart_hours), default=1) or 1

    context = {
        "online_now": online_now,
        "visitors_today": visitors_today,
        "pageviews_today": pageviews_today,
        "new_users_today": new_users_today,
        "active_users_today": active_users_today,
        "count_404_today": count_404_today,
        "failed_logins_today": failed_logins_today,
        "suspicious_today": suspicious_today,
        "top_recipes": top_recipes,
        "top_articles": top_articles,
        "top_paths": top_paths,
        "top_referrers": top_referrers,
        "latest_activities": latest_activities,
        "latest_security": latest_security,
        "chart_hours": chart_hours,
        "chart_max": chart_max,
        "today": today,
    }
    return render(request, "monitoring/dashboard.html", context)
