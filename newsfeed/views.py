from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from .forms import NewsFeedEntryForm
from .models import NewsFeedEntry

_PAGE_SIZE = 30


def feed(request):
    entries = NewsFeedEntry.objects.filter(is_public=True).order_by("-published_at")
    paginator = Paginator(entries, _PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "newsfeed/feed.html", {
        "page_obj": page_obj,
    })


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
