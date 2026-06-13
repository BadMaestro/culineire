from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import redirect, render

from .forms import NewsFeedEntryForm
from .models import NewsFeedEntry

_PAGE_SIZE = 30

_FEED_FILTERS = (
    ("all", "All", ()),
    ("recipes", "Recipes", (NewsFeedEntry.EntryType.RECIPE_PUBLISHED,)),
    ("articles", "Articles", (NewsFeedEntry.EntryType.ARTICLE_PUBLISHED,)),
    (
        "amuse-bouche",
        "Amuse-Bouche",
        (
            NewsFeedEntry.EntryType.AMUSE_BOUCHE_PUBLISHED,
            NewsFeedEntry.EntryType.AMUSE_BOUCHE_FEATURED,
        ),
    ),
    ("battle", "Chef Battle", (NewsFeedEntry.EntryType.BATTLE_EVENT,)),
    (
        "site",
        "Site Updates",
        (
            NewsFeedEntry.EntryType.SITE_UPDATE,
            NewsFeedEntry.EntryType.SECURITY_UPDATE,
            NewsFeedEntry.EntryType.VERSION_RELEASE,
            NewsFeedEntry.EntryType.ADMIN_NOTE,
        ),
    ),
)


def feed(request):
    base_entries = NewsFeedEntry.objects.filter(is_public=True).order_by("-published_at")
    active_filter = request.GET.get("type", "all")
    filter_map = {key: tuple(entry_types) for key, _label, entry_types in _FEED_FILTERS}
    if active_filter not in filter_map:
        active_filter = "all"

    entries = base_entries
    if filter_map[active_filter]:
        entries = entries.filter(entry_type__in=filter_map[active_filter])

    counts_by_type = dict(
        base_entries.values("entry_type")
        .annotate(total=Count("id"))
        .values_list("entry_type", "total")
    )
    feed_filters = []
    for key, label, entry_types in _FEED_FILTERS:
        count = (
            sum(counts_by_type.get(entry_type, 0) for entry_type in entry_types)
            if entry_types
            else sum(counts_by_type.values())
        )
        feed_filters.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "is_active": key == active_filter,
                "url": "?" if key == "all" else f"?type={key}",
            }
        )

    story_count = sum(
        counts_by_type.get(entry_type, 0)
        for entry_type in (
            NewsFeedEntry.EntryType.RECIPE_PUBLISHED,
            NewsFeedEntry.EntryType.ARTICLE_PUBLISHED,
            NewsFeedEntry.EntryType.AMUSE_BOUCHE_PUBLISHED,
            NewsFeedEntry.EntryType.AMUSE_BOUCHE_FEATURED,
        )
    )
    site_update_count = sum(
        counts_by_type.get(entry_type, 0) for entry_type in filter_map["site"]
    )
    battle_count = counts_by_type.get(NewsFeedEntry.EntryType.BATTLE_EVENT, 0)

    paginator = Paginator(entries, _PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    pagination_prefix = f"?type={active_filter}&page=" if active_filter != "all" else "?page="

    return render(
        request,
        "newsfeed/feed.html",
        {
            "active_filter": active_filter,
            "feed_filters": feed_filters,
            "latest_entry": base_entries.first(),
            "page_obj": page_obj,
            "pagination_prefix": pagination_prefix,
            "summary": {
                "total": sum(counts_by_type.values()),
                "stories": story_count,
                "site_updates": site_update_count,
                "battle_events": battle_count,
            },
        },
    )


@login_required
def add_entry(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == "POST":
        form = NewsFeedEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.created_by = request.user
            entry.save()
            return redirect("newsfeed:feed")
    else:
        form = NewsFeedEntryForm()

    return render(request, "newsfeed/add_entry.html", {"form": form})
