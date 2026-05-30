from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, F, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView
from django_ratelimit.decorators import ratelimit

from collection.models import ContentReaction, SavedContent
from monitoring.tracker import track_event
from recipes.authoring import AuthorRequiredMixin, user_can_manage_author
from .forms import AmuseBoucheAuthoringForm
from .models import AmuseBouche, AmuseBoucheGalleryImage
from .visibility import can_view_amuse_bouche_public_area


def _require_public_area_access(request):
    if not can_view_amuse_bouche_public_area(request.user):
        raise Http404


def _public_queryset():
    return (
        AmuseBouche.objects.filter(status=AmuseBouche.Status.APPROVED)
        .select_related("author", "linked_recipe", "linked_article")
        .prefetch_related(
            Prefetch(
                "gallery_images",
                queryset=AmuseBoucheGalleryImage.objects.filter(is_active=True).order_by("sort_order", "id"),
                to_attr="active_gallery_images",
            )
        )
        .annotate(like_total=Count("reactions", filter=Q(reactions__reaction=ContentReaction.Reaction.LIKE), distinct=True))
        .annotate(save_total=Count("saves", distinct=True))
    )


def _user_state(queryset, user):
    items = list(queryset)
    if not user.is_authenticated or not items:
        return items, set(), set()
    content_type = ContentType.objects.get_for_model(AmuseBouche)
    object_ids = [item.pk for item in items]
    liked_ids = set(
        ContentReaction.objects.filter(
            user=user,
            content_type=content_type,
            object_id__in=object_ids,
            reaction=ContentReaction.Reaction.LIKE,
        ).values_list("object_id", flat=True)
    )
    saved_ids = set(
        SavedContent.objects.filter(user=user, content_type=content_type, object_id__in=object_ids)
        .values_list("object_id", flat=True)
    )
    return items, liked_ids, saved_ids


def feed(request):
    _require_public_area_access(request)
    content_type = request.GET.get("type", "")
    author = request.GET.get("author", "")
    queryset = _public_queryset()
    if content_type:
        queryset = queryset.filter(content_type=content_type)
    if author:
        queryset = queryset.filter(author__slug=author)
    items, liked_ids, saved_ids = _user_state(queryset[:30], request.user)
    return render(request, "amuse_bouche/feed.html", {
        "items": items,
        "content_type_choices": AmuseBouche.ContentType.choices,
        "active_content_type": content_type,
        "liked_ids": liked_ids,
        "saved_ids": saved_ids,
    })


def detail(request, slug):
    _require_public_area_access(request)
    item = get_object_or_404(_public_queryset(), slug=slug)
    AmuseBouche.objects.filter(pk=item.pk).update(view_count=F("view_count") + 1)
    items, liked_ids, saved_ids = _user_state([item], request.user)
    return render(request, "amuse_bouche/detail.html", {
        "item": items[0],
        "liked_ids": liked_ids,
        "saved_ids": saved_ids,
    })


class AmuseBoucheCreateView(AuthorRequiredMixin, CreateView):
    model = AmuseBouche
    form_class = AmuseBoucheAuthoringForm
    template_name = "amuse_bouche/form.html"
    success_url = reverse_lazy("amuse_bouche:feed")

    def dispatch(self, request, *args, **kwargs):
        _require_public_area_access(request)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["author"] = self.author
        return kwargs

    def form_valid(self, form):
        item = form.save(commit=False)
        item.author = self.author
        item.status = AmuseBouche.Status.PENDING
        response = super().form_valid(form)
        messages.success(self.request, "Your Amuse-Bouche was submitted for review.")
        return response


@method_decorator(login_required, name="dispatch")
class AmuseBoucheUpdateView(AuthorRequiredMixin, UpdateView):
    model = AmuseBouche
    form_class = AmuseBoucheAuthoringForm
    template_name = "amuse_bouche/form.html"

    def dispatch(self, request, *args, **kwargs):
        _require_public_area_access(request)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return AmuseBouche.objects.filter(author=self.author)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["author"] = self.author
        return kwargs

    def form_valid(self, form):
        item = form.save(commit=False)
        if not user_can_manage_author(self.request.user, item.author):
            return redirect(item.get_absolute_url())
        if item.status == AmuseBouche.Status.APPROVED:
            item.status = AmuseBouche.Status.PENDING
        response = super().form_valid(form)
        messages.success(self.request, "Amuse-Bouche updated.")
        return response


def _safe_next(request, fallback):
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(fallback)


@require_POST
@login_required
@ratelimit(key="user", rate="90/h", method="POST", block=False)
def toggle_like(request, slug):
    _require_public_area_access(request)
    item = get_object_or_404(AmuseBouche, slug=slug, status=AmuseBouche.Status.APPROVED)
    if getattr(request, "limited", False):
        messages.error(request, "Too many requests. Please try again later.")
        return _safe_next(request, item.get_absolute_url())
    content_type = ContentType.objects.get_for_model(AmuseBouche)
    reaction, created = ContentReaction.objects.get_or_create(
        user=request.user,
        content_type=content_type,
        object_id=item.pk,
        reaction=ContentReaction.Reaction.LIKE,
    )
    if created:
        track_event(request, "content_like", object_type="amuse_bouche", object_id=item.pk, object_title=item.title)
        messages.success(request, "Liked.")
    else:
        reaction.delete()
        messages.success(request, "Like removed.")
    return _safe_next(request, item.get_absolute_url())


@require_POST
@login_required
@ratelimit(key="user", rate="90/h", method="POST", block=False)
def toggle_save(request, slug):
    _require_public_area_access(request)
    item = get_object_or_404(AmuseBouche, slug=slug, status=AmuseBouche.Status.APPROVED)
    if getattr(request, "limited", False):
        messages.error(request, "Too many requests. Please try again later.")
        return _safe_next(request, item.get_absolute_url())
    content_type = ContentType.objects.get_for_model(AmuseBouche)
    saved, created = SavedContent.objects.get_or_create(
        user=request.user,
        content_type=content_type,
        object_id=item.pk,
    )
    if created:
        track_event(request, "collection_add", object_type="amuse_bouche", object_id=item.pk, object_title=item.title)
        messages.success(request, "Added to your collection.")
    else:
        saved.delete()
        track_event(request, "collection_remove", object_type="amuse_bouche", object_id=item.pk, object_title=item.title)
        messages.success(request, "Removed from your collection.")
    return _safe_next(request, item.get_absolute_url())
