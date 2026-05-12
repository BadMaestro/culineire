from django.core.paginator import Paginator
from django.shortcuts import render

from .models import NewsFeedEntry

_PAGE_SIZE = 30


def feed(request):
    entries = NewsFeedEntry.objects.filter(is_public=True).order_by("-published_at")
    paginator = Paginator(entries, _PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "newsfeed/feed.html", {
        "page_obj": page_obj,
    })
