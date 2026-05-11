from __future__ import annotations

from collections import Counter

from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.functions import ExtractHour
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from recipes.views import is_moderator

from .models import PageView, SecurityEvent, UserActivity

DETAIL_PAGE_SIZE = 100
DETAIL_ROW_LIMIT = 3000
HUMAN_REQUEST_KINDS = {"Human", "Guest/Browser"}

BOT_USER_AGENT_MARKERS = (
    "bot",
    "crawler",
    "spider",
    "crawl",
    "censys",
    "claudebot",
    "bytespider",
    "semrush",
    "ahrefs",
    "mj12bot",
    "bingpreview",
    "facebookexternalhit",
    "telegrambot",
    "curl/",
    "wget/",
    "python-requests",
    "go-http-client",
    "httpx",
    "okhttp",
)

TECHNICAL_PATHS = (
    "/sitemap.xml",
    "/robots.txt",
    "/favicon.ico",
    "/favicon.png",
    "/apple-touch-icon.png",
)

SUSPICIOUS_PATH_MARKERS = (
    ".env",
    ".git",
    ".hg",
    ".svn",
    ".sql",
    ".log",
    ".bak",
    ".swp",
    "wp-",
    "xmlrpc",
    "phpmy",
    ".php",
    "graphql",
    "swagger",
    "server-status",
    "server-info",
    "actuator",
    "bitbucket-pipelines.yml",
    "amplify.yml",
    "serverless.yml",
    "serverless.yaml",
    "dockerfile",
    "jenkinsfile",
    "composer.json",
    "package.json",
    "vite.config",
    "nuxt.config",
    "next.config",
    "webpack.config",
    "firebase-debug",
    "database",
    "backup",
    "dump",
    "/logs/",
    "/var/log/",
    "/storage/logs/",
    "/%22/",
    '/"/',
    "/https:/",
)

PROTECTED_PATH_PREFIXES = (
    "/admin/",
    "/recipes/moderation/",
)

PERIOD_OPTIONS = {
    "today": "Today",
    "24h": "Last 24 hours",
    "7d": "Last 7 days",
}


def _require_moderator(request):
    if not is_moderator(request.user):
        raise Http404


def _is_bot_user_agent(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    return any(marker in ua for marker in BOT_USER_AGENT_MARKERS)


def _is_technical_path(path: str) -> bool:
    return path in TECHNICAL_PATHS


def _is_suspicious_path(path: str) -> bool:
    normalized = (path or "").lower()
    return any(marker in normalized for marker in SUSPICIOUS_PATH_MARKERS)


def _is_protected_path(path: str) -> bool:
    normalized = path or ""
    return any(normalized.startswith(prefix) for prefix in PROTECTED_PATH_PREFIXES)


def _request_kind(user_agent: str, path: str, user=None) -> str:
    if user is not None:
        return "Human"
    if _is_bot_user_agent(user_agent) or _is_technical_path(path) or _is_suspicious_path(path):
        return "Bot/Scanner"
    if _is_protected_path(path):
        return "Protected Area"
    if user_agent:
        return "Guest/Browser"
    return "Unknown"


def _kind_class(label: str) -> str:
    return label.lower().replace("/", "-").replace(" ", "-")


def _decorate_request_rows(rows):
    for row in rows:
        label = _request_kind(
            getattr(row, "user_agent", ""),
            getattr(row, "path", ""),
            getattr(row, "user", None),
        )
        row.request_kind = label
        row.request_kind_class = _kind_class(label)
    return rows


def _period_bounds(period: str, now):
    if period == "24h":
        return {"created_at__gte": now - timezone.timedelta(hours=24)}
    if period == "7d":
        return {"created_at__gte": now - timezone.timedelta(days=7)}
    return {"created_at__date": timezone.localdate()}


def _selected_period(request) -> str:
    period = request.GET.get("period", "today")
    if period not in PERIOD_OPTIONS:
        return "today"
    return period


def _period_links(base_url: str, selected: str, extra_query: str = ""):
    links = []
    separator = "&" if extra_query else ""
    for key, label in PERIOD_OPTIONS.items():
        links.append({
            "key": key,
            "label": label,
            "url": f"{base_url}?period={key}{separator}{extra_query}",
            "active": key == selected,
        })
    return links


def _paginate(request, rows_or_qs):
    paginator = Paginator(rows_or_qs, DETAIL_PAGE_SIZE)
    return paginator.get_page(request.GET.get("page"))


def _dashboard_url(name: str, query: str = "") -> str:
    url = reverse(name)
    return f"{url}?{query}" if query else url


def _content_url_maps(recipe_ids, article_ids):
    recipe_urls = {}
    article_urls = {}
    if recipe_ids:
        from recipes.models import Recipe

        for recipe in Recipe.objects.filter(pk__in=recipe_ids).only("pk", "slug"):
            recipe_urls[recipe.pk] = reverse("recipes:recipe_detail", kwargs={"slug": recipe.slug})
    if article_ids:
        from articles.models import Article

        for article in Article.objects.filter(pk__in=article_ids).only("pk", "slug"):
            article_urls[article.pk] = reverse("articles:article_detail", kwargs={"slug": article.slug})
    return recipe_urls, article_urls


def dashboard(request):
    _require_moderator(request)

    now = timezone.now()
    today = timezone.localdate()
    five_min_ago = now - timezone.timedelta(minutes=5)
    seven_days_ago = now - timezone.timedelta(days=7)

    today_pageviews = list(
        PageView.objects
        .filter(created_at__date=today)
        .select_related("user")
        .only("path", "user_agent", "user")
    )
    decorated_today_pageviews = _decorate_request_rows(today_pageviews)
    human_pageviews_today = sum(1 for row in decorated_today_pageviews if row.request_kind in HUMAN_REQUEST_KINDS)
    bot_pageviews_today = sum(1 for row in decorated_today_pageviews if row.request_kind == "Bot/Scanner")

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

    pageviews_today = len(today_pageviews)

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

    top_recipe_rows = list(
        UserActivity.objects
        .filter(event_type=UserActivity.EventType.RECIPE_VIEW, object_type="recipe")
        .values("object_id", "object_title")
        .annotate(views=Count("id"))
        .order_by("-views")[:10]
    )
    top_article_rows = list(
        UserActivity.objects
        .filter(event_type=UserActivity.EventType.ARTICLE_VIEW, object_type="article")
        .values("object_id", "object_title")
        .annotate(views=Count("id"))
        .order_by("-views")[:10]
    )
    recipe_urls, article_urls = _content_url_maps(
        [row["object_id"] for row in top_recipe_rows if row["object_id"]],
        [row["object_id"] for row in top_article_rows if row["object_id"]],
    )

    seen_recipe_ids: set[int] = set()
    top_recipes = []
    for row in top_recipe_rows:
        if row["object_id"] not in seen_recipe_ids:
            seen_recipe_ids.add(row["object_id"])
            row["url"] = recipe_urls.get(row["object_id"], "")
            top_recipes.append(row)

    seen_article_ids: set[int] = set()
    top_articles = []
    for row in top_article_rows:
        if row["object_id"] not in seen_article_ids:
            seen_article_ids.add(row["object_id"])
            row["url"] = article_urls.get(row["object_id"], "")
            top_articles.append(row)

    top_paths = (
        PageView.objects
        .filter(created_at__gte=seven_days_ago)
        .values("path")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    top_referrers = (
        PageView.objects
        .filter(created_at__gte=seven_days_ago)
        .exclude(referrer="")
        .values("referrer")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    latest_activities = (
        UserActivity.objects
        .select_related("user")
        .order_by("-created_at")[:25]
    )

    latest_security = list(
        SecurityEvent.objects
        .select_related("user")
        .order_by("-created_at")[:25]
    )
    _decorate_request_rows(latest_security)

    hourly_views = list(
        PageView.objects
        .filter(created_at__date=today)
        .annotate(hour=ExtractHour("created_at"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    hourly_map = {
        f"{int(row['hour']):02d}": row["count"]
        for row in hourly_views
        if row["hour"] is not None
    }
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
        "human_pageviews_today": human_pageviews_today,
        "bot_pageviews_today": bot_pageviews_today,
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
        "traffic_urls": {
            "online": _dashboard_url("monitoring:traffic_detail", "kind=online"),
            "visitors": _dashboard_url("monitoring:traffic_detail", "kind=visitors"),
            "pageviews": _dashboard_url("monitoring:traffic_detail", "kind=pageviews"),
            "human": _dashboard_url("monitoring:traffic_detail", "kind=human"),
            "bots": _dashboard_url("monitoring:traffic_detail", "kind=bots"),
        },
        "activity_urls": {
            "new_users": _dashboard_url("monitoring:activity_detail", "kind=new-users"),
            "active_users": _dashboard_url("monitoring:activity_detail", "kind=active-users"),
            "all": reverse("monitoring:activity_detail"),
        },
        "security_urls": {
            "404": _dashboard_url("monitoring:security_detail", "event=404"),
            "failed_login": _dashboard_url("monitoring:security_detail", "event=failed_login"),
            "suspicious": _dashboard_url("monitoring:security_detail", "event=suspicious_request"),
            "all": reverse("monitoring:security_detail"),
        },
    }
    return render(request, "monitoring/dashboard.html", context)


def traffic_detail(request):
    _require_moderator(request)

    now = timezone.now()
    period = _selected_period(request)
    kind = request.GET.get("kind", "pageviews")
    path_filter = request.GET.get("path", "")
    ip_hash_filter = request.GET.get("ip_hash", "")

    qs = (
        PageView.objects
        .select_related("user")
        .filter(**_period_bounds(period, now))
        .order_by("-created_at")
    )
    if path_filter:
        qs = qs.filter(path=path_filter)
    if ip_hash_filter:
        qs = qs.filter(ip_hash=ip_hash_filter)

    if kind == "online":
        qs = qs.filter(created_at__gte=now - timezone.timedelta(minutes=5)).exclude(session_key="")
        title = "Online Sessions"
        subtitle = "Requests from sessions active in the last 5 minutes."
    elif kind == "visitors":
        qs = qs.exclude(session_key="")
        title = "Visitors"
        subtitle = "Requests grouped by browser session signal."
    elif kind == "human":
        title = "Human and Guest Page Views"
        subtitle = "Logged-in users and normal anonymous browser traffic. Scanner-like paths are excluded."
    elif kind == "bots":
        title = "Bot and Crawler Page Views"
        subtitle = "Successful requests with bot-like user agents or technical paths."
    else:
        kind = "pageviews"
        title = "Page Views"
        subtitle = "Successful page requests recorded by CulinEire monitoring."

    needs_python_filter = kind in {"human", "bots"}
    if needs_python_filter:
        rows = list(qs[:DETAIL_ROW_LIMIT])
        _decorate_request_rows(rows)
        if kind == "human":
            rows = [row for row in rows if row.request_kind in HUMAN_REQUEST_KINDS]
        else:
            rows = [row for row in rows if row.request_kind == "Bot/Scanner"]
        page_obj = _paginate(request, rows)
        total_count = len(rows)
        top_paths = [
            {"path": path, "count": count}
            for path, count in Counter(row.path for row in rows).most_common(10)
        ]
    else:
        total_count = qs.count()
        page_obj = _paginate(request, qs)
        page_obj.object_list = _decorate_request_rows(list(page_obj.object_list))
        top_paths = list(
            qs.values("path").annotate(count=Count("id")).order_by("-count")[:10]
        )

    context = {
        "detail_type": "traffic",
        "title": title,
        "subtitle": subtitle,
        "period": period,
        "period_label": PERIOD_OPTIONS[period],
        "period_links": _period_links(
            reverse("monitoring:traffic_detail"),
            period,
            f"kind={kind}",
        ),
        "kind": kind,
        "path_filter": path_filter,
        "ip_hash_filter": ip_hash_filter,
        "total_count": total_count,
        "page_obj": page_obj,
        "top_paths": top_paths,
        "ip_filter_url_base": (
            f"{reverse('monitoring:traffic_detail')}?period={period}&kind={kind}&ip_hash="
        ),
        "path_filter_url_base": (
            f"{reverse('monitoring:traffic_detail')}?period={period}&kind={kind}&path="
        ),
        "dashboard_url": reverse("monitoring:dashboard"),
    }
    return render(request, "monitoring/detail.html", context)


def security_detail(request):
    _require_moderator(request)

    now = timezone.now()
    period = _selected_period(request)
    event = request.GET.get("event", "all")
    ip_hash_filter = request.GET.get("ip_hash", "")
    path_filter = request.GET.get("path", "")

    qs = (
        SecurityEvent.objects
        .select_related("user")
        .filter(**_period_bounds(period, now))
        .order_by("-created_at")
    )
    valid_events = {choice[0] for choice in SecurityEvent.EventType.choices}
    if event in valid_events:
        qs = qs.filter(event_type=event)
    else:
        event = "all"
    if ip_hash_filter:
        qs = qs.filter(ip_hash=ip_hash_filter)
    if path_filter:
        qs = qs.filter(path=path_filter)

    page_obj = _paginate(request, qs)
    page_obj.object_list = _decorate_request_rows(list(page_obj.object_list))
    event_counts = qs.values("event_type").annotate(count=Count("id")).order_by("-count")

    context = {
        "detail_type": "security",
        "title": "Security Events",
        "subtitle": "404s, forbidden requests, suspicious probes and failed login records.",
        "period": period,
        "period_label": PERIOD_OPTIONS[period],
        "period_links": _period_links(
            reverse("monitoring:security_detail"),
            period,
            f"event={event}",
        ),
        "event": event,
        "ip_hash_filter": ip_hash_filter,
        "path_filter": path_filter,
        "total_count": qs.count(),
        "page_obj": page_obj,
        "event_counts": event_counts,
        "ip_filter_url_base": (
            f"{reverse('monitoring:security_detail')}?period={period}&event={event}&ip_hash="
        ),
        "path_filter_url_base": (
            f"{reverse('monitoring:security_detail')}?period={period}&event={event}&path="
        ),
        "dashboard_url": reverse("monitoring:dashboard"),
    }
    return render(request, "monitoring/detail.html", context)


def activity_detail(request):
    _require_moderator(request)

    now = timezone.now()
    period = _selected_period(request)
    kind = request.GET.get("kind", "all")

    qs = (
        UserActivity.objects
        .select_related("user")
        .filter(**_period_bounds(period, now))
        .order_by("-created_at")
    )

    if kind == "new-users":
        qs = qs.filter(event_type=UserActivity.EventType.REGISTER)
        title = "New Users"
        subtitle = "Registration activity for the selected period."
    elif kind == "active-users":
        qs = qs.exclude(user=None)
        title = "Active Users"
        subtitle = "Logged-in user activity for the selected period."
    else:
        kind = "all"
        title = "User Activity"
        subtitle = "Logins, registrations, profile updates and content activity."

    page_obj = _paginate(request, qs)
    event_counts = qs.values("event_type").annotate(count=Count("id")).order_by("-count")

    context = {
        "detail_type": "activity",
        "title": title,
        "subtitle": subtitle,
        "period": period,
        "period_label": PERIOD_OPTIONS[period],
        "period_links": _period_links(
            reverse("monitoring:activity_detail"),
            period,
            f"kind={kind}",
        ),
        "kind": kind,
        "total_count": qs.count(),
        "page_obj": page_obj,
        "event_counts": event_counts,
        "dashboard_url": reverse("monitoring:dashboard"),
    }
    return render(request, "monitoring/detail.html", context)
