from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, F, Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DeleteView, UpdateView
from django_ratelimit.decorators import ratelimit

from collection.models import AuthorFollow, ContentReaction, SavedContent
from monitoring.tracker import track_event
from recipes.authoring import AuthorRequiredMixin, author_skips_approval, user_can_manage_author
from recipes.models import RecipeAuthor
from articles.models import Article
from recipes.models import Recipe
from accounts.views import is_moderator
from .forms import AmuseBoucheAuthoringForm
from .models import AmuseBouche, AmuseBoucheComment, AmuseBoucheGalleryImage
from .telegram_preview import get_telegram_preview_meta
from .visibility import can_view_amuse_bouche_public_area


def _require_public_area_access(request):
    if not can_view_amuse_bouche_public_area(request.user):
        raise Http404


def _can_preview_item(user, item):
    return is_moderator(user) or user_can_manage_author(user, item.author)


def _initial_status_for_author(author):
    if author_skips_approval(author):
        return AmuseBouche.Status.APPROVED
    return AmuseBouche.Status.PENDING


def _initial_status_fields(author, actor):
    status = _initial_status_for_author(author)
    fields = {"status": status}
    if status == AmuseBouche.Status.APPROVED:
        now = timezone.now()
        fields["moderated_by"] = actor
        fields["moderated_at"] = now
        fields["published_at"] = now
    return fields


def _created_message(item, pending_message):
    if item.status == AmuseBouche.Status.APPROVED:
        return f'Amuse-Bouche "{item.title}" approved and is now live.'
    return pending_message


def _public_queryset(approved_only=True):
    queryset = AmuseBouche.objects.all()
    if approved_only:
        queryset = queryset.filter(status=AmuseBouche.Status.APPROVED)
    return (
        queryset
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
        .annotate(comment_total=Count("comments", filter=Q(comments__is_deleted=False), distinct=True))
    )


def _user_state(queryset, user):
    """Return (items, liked_ids, saved_ids, followed_author_ids)."""
    items = list(queryset)
    if not user.is_authenticated or not items:
        return items, set(), set(), set()
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
    author_ids = {item.author_id for item in items if item.author_id}
    followed_author_ids = set(
        AuthorFollow.objects.filter(user=user, author_id__in=author_ids)
        .values_list("author_id", flat=True)
    )
    return items, liked_ids, saved_ids, followed_author_ids


def _likers_by_item(items):
    """Return a dict {item_pk: [RecipeAuthor, ...]} with up to 3 authors who liked each item."""
    from collections import defaultdict
    if not items:
        return {}
    ct = ContentType.objects.get_for_model(AmuseBouche)
    item_ids = [item.pk for item in items]
    reactions = (
        ContentReaction.objects.filter(
            content_type=ct,
            object_id__in=item_ids,
            reaction=ContentReaction.Reaction.LIKE,
        )
        .values("object_id", "user_id")
        .order_by("object_id", "-created_at")
    )
    item_user_ids: dict = defaultdict(list)
    for row in reactions:
        lst = item_user_ids[row["object_id"]]
        if len(lst) < 3:
            lst.append(row["user_id"])
    all_user_ids = {uid for uids in item_user_ids.values() for uid in uids}
    author_by_user = {
        a.user_id: a
        for a in RecipeAuthor.objects.filter(user_id__in=all_user_ids)
    }
    return {
        item_id: [author_by_user[uid] for uid in uids if uid in author_by_user]
        for item_id, uids in item_user_ids.items()
    }


def _attach_likers(items):
    """Attach a .liker_authors list (up to 3 RecipeAuthors) to each item in-place."""
    likers_map = _likers_by_item(items)
    for item in items:
        item.liker_authors = likers_map.get(item.pk, [])


def feed(request):
    _require_public_area_access(request)
    content_type = request.GET.get("type", "")
    author = request.GET.get("author", "").strip()
    queryset = _public_queryset()
    if content_type:
        queryset = queryset.filter(content_type=content_type)
    if author:
        queryset = queryset.filter(author__slug=author)
    items, liked_ids, saved_ids, followed_author_ids = _user_state(queryset[:30], request.user)
    _attach_likers(items)
    user_author_slug = ""
    if request.user.is_authenticated:
        profile = getattr(request.user, "recipe_author_profile", None)
        user_author_slug = profile.slug if profile else ""
    show_author_create_action = bool(user_author_slug and author == user_author_slug)
    return render(request, "amuse_bouche/feed.html", {
        "items": items,
        "content_type_choices": AmuseBouche.ContentType.choices,
        "active_content_type": content_type,
        "liked_ids": liked_ids,
        "saved_ids": saved_ids,
        "followed_author_ids": followed_author_ids,
        "user_author_slug": user_author_slug,
        "user_is_moderator": is_moderator(request.user),
        "show_author_create_action": show_author_create_action,
        "dashboard_back_url": reverse("recipes:author_dashboard") if show_author_create_action else "",
    })


def detail(request, slug):
    if is_moderator(request.user):
        queryset = _public_queryset(approved_only=False).exclude(status=AmuseBouche.Status.ARCHIVED)
    elif request.user.is_authenticated:
        queryset = _public_queryset(approved_only=False).exclude(status=AmuseBouche.Status.ARCHIVED)
    else:
        _require_public_area_access(request)
        queryset = _public_queryset()
    item = get_object_or_404(queryset, slug=slug)
    can_preview = _can_preview_item(request.user, item)
    if item.status == AmuseBouche.Status.APPROVED:
        if not can_view_amuse_bouche_public_area(request.user) and not can_preview:
            raise Http404
    elif not can_preview:
        raise Http404
    AmuseBouche.objects.filter(pk=item.pk).update(view_count=F("view_count") + 1)
    items, liked_ids, saved_ids, followed_author_ids = _user_state([item], request.user)
    _attach_likers(items)
    can_moderate = is_moderator(request.user)
    can_edit = can_moderate or user_can_manage_author(request.user, item.author)
    comments = (
        AmuseBoucheComment.objects.filter(amuse_bouche=item, is_deleted=False)
        .select_related("user", "user__recipe_author_profile")
        .order_by("created_at")
        if item.allow_comments else []
    )
    return render(request, "amuse_bouche/detail.html", {
        "item": items[0],
        "telegram_preview_image": get_telegram_preview_meta(items[0], request=request),
        "liked_ids": liked_ids,
        "saved_ids": saved_ids,
        "followed_author_ids": followed_author_ids,
        "can_moderate": can_moderate,
        "can_edit": can_edit,
        "comments": comments,
        "can_view_ab_public": can_view_amuse_bouche_public_area(request.user),
    })


class AmuseBoucheCreateView(AuthorRequiredMixin, CreateView):
    model = AmuseBouche
    form_class = AmuseBoucheAuthoringForm
    template_name = "amuse_bouche/form.html"
    success_url = reverse_lazy("amuse_bouche:feed")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["author"] = self.author
        return kwargs

    def form_valid(self, form):
        item = form.save(commit=False, confirmed_by=self.request.user)
        item.author = self.author
        for field, value in _initial_status_fields(self.author, self.request.user).items():
            setattr(item, field, value)
        item.save()
        messages.success(
            self.request,
            _created_message(item, "Your Amuse-Bouche was submitted for review."),
        )
        return redirect(item.get_absolute_url())

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["author"] = self.author
        ctx["cancel_url"] = self.author.get_absolute_url()
        return ctx


@method_decorator(login_required, name="dispatch")
class AmuseBoucheUpdateView(AuthorRequiredMixin, UpdateView):
    model = AmuseBouche
    form_class = AmuseBoucheAuthoringForm
    template_name = "amuse_bouche/form.html"

    def get_queryset(self):
        return AmuseBouche.objects.filter(author=self.author)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["author"] = self.author
        return kwargs

    def form_valid(self, form):
        item = form.save(commit=False, confirmed_by=self.request.user)
        if not user_can_manage_author(self.request.user, item.author):
            return redirect(item.get_absolute_url())
        # Moderators save directly — no status reset needed
        if item.status == AmuseBouche.Status.APPROVED and not is_moderator(self.request.user):
            item.status = AmuseBouche.Status.PENDING
        item.save()
        messages.success(self.request, "Amuse-Bouche updated.")
        return redirect(item.get_absolute_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["author"] = self.author
        ctx["cancel_url"] = self.object.get_absolute_url()
        ctx["is_moderator"] = is_moderator(self.request.user)
        ctx["from_recipe"] = self.request.GET.get("from_recipe") == "1"
        ctx["from_article"] = self.request.GET.get("from_article") == "1"
        if not self.object.cover_image:
            item = self.object
            if item.linked_recipe_id and item.linked_recipe.hero_image:
                ctx["inherited_image_url"] = item.linked_recipe.hero_image.url
                ctx["inherited_image_label"] = "Image inherited from recipe"
            elif item.linked_article_id and item.linked_article.hero_image:
                ctx["inherited_image_url"] = item.linked_article.hero_image.url
                ctx["inherited_image_label"] = "Image inherited from article"
        return ctx


class AmuseBoucheDeleteView(AuthorRequiredMixin, DeleteView):
    model = AmuseBouche
    template_name = "authoring/confirm_delete.html"
    context_object_name = "managed_object"

    def get_success_url(self):
        from django.urls import reverse
        return reverse("amuse_bouche:feed") + f"?author={self.author.slug}"

    def get_queryset(self):
        if is_moderator(self.request.user):
            return AmuseBouche.objects.all()
        return AmuseBouche.objects.filter(author=self.author)

    def form_valid(self, form):
        messages.success(self.request, "Amuse-Bouche deleted.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["author"] = self.author
        ctx["delete_title"] = "Delete Amuse-Bouche"
        ctx["delete_intro"] = (
            f'You are about to delete "{self.object.title}". This action cannot be undone.'
        )
        ctx["delete_label"] = "Delete Amuse-Bouche"
        ctx["cancel_url"] = self.object.get_absolute_url()
        return ctx


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
    is_fetch = request.headers.get("X-AB-Fetch") == "1"
    if getattr(request, "limited", False):
        if is_fetch:
            return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)
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
    else:
        reaction.delete()
    if is_fetch:
        count = ContentReaction.objects.filter(
            content_type=content_type,
            object_id=item.pk,
            reaction=ContentReaction.Reaction.LIKE,
        ).count()
        return JsonResponse({"ok": True, "liked": created, "count": count})
    if created:
        messages.success(request, "Liked.")
    else:
        messages.success(request, "Like removed.")
    return _safe_next(request, item.get_absolute_url())


@require_POST
@login_required
@ratelimit(key="user", rate="90/h", method="POST", block=False)
def toggle_save(request, slug):
    _require_public_area_access(request)
    item = get_object_or_404(AmuseBouche, slug=slug, status=AmuseBouche.Status.APPROVED)
    is_fetch = request.headers.get("X-AB-Fetch") == "1"
    if getattr(request, "limited", False):
        if is_fetch:
            return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)
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
    else:
        saved.delete()
        track_event(request, "collection_remove", object_type="amuse_bouche", object_id=item.pk, object_title=item.title)
    if is_fetch:
        return JsonResponse({"ok": True, "saved": created})
    if created:
        messages.success(request, "Added to your collection.")
    else:
        messages.success(request, "Removed from your collection.")
    return _safe_next(request, item.get_absolute_url())


@require_POST
@login_required
def moderate(request, slug):
    if not is_moderator(request.user):
        raise Http404

    item = get_object_or_404(AmuseBouche, slug=slug)
    action = request.POST.get("action")

    if action == "approve":
        item.status = AmuseBouche.Status.APPROVED
        item.moderation_note = ""
        item.moderated_by = request.user
        item.moderated_at = timezone.now()
        item.save(update_fields=["status", "moderation_note", "moderated_by", "moderated_at", "published_at", "updated_at"])
        messages.success(request, f'"{item.title}" approved and is now live.')
    elif action == "request_changes":
        note = request.POST.get("moderation_note", "").strip()
        if not note:
            messages.error(request, "A moderation note is required. Please explain what needs to be changed.")
            return redirect(item.get_absolute_url())
        item.status = AmuseBouche.Status.NEEDS_CHANGES
        item.moderation_note = note
        item.moderated_by = request.user
        item.moderated_at = timezone.now()
        item.save(update_fields=["status", "moderation_note", "moderated_by", "moderated_at", "updated_at"])
        messages.warning(request, f'Changes requested for "{item.title}".')
    elif action == "reject":
        note = request.POST.get("moderation_note", "").strip()
        if not note:
            messages.error(request, "A rejection note is required. Please explain what needs to be corrected.")
            return redirect(item.get_absolute_url())
        item.status = AmuseBouche.Status.REJECTED
        item.moderation_note = note
        item.moderated_by = request.user
        item.moderated_at = timezone.now()
        item.save(update_fields=["status", "moderation_note", "moderated_by", "moderated_at", "updated_at"])
        messages.warning(request, f'"{item.title}" rejected.')
    elif action == "delete":
        title = item.title
        item.status = AmuseBouche.Status.ARCHIVED
        item.moderation_note = ""
        item.moderated_by = request.user
        item.moderated_at = timezone.now()
        item.save(update_fields=["status", "moderation_note", "moderated_by", "moderated_at", "updated_at"])
        messages.success(request, f'"{title}" archived.')
        return redirect("recipes:moderation_panel")
    else:
        raise Http404

    return redirect(item.get_absolute_url())


@require_POST
@login_required
def generate_from_recipe(request, slug):
    """Create an Amuse-Bouche pre-filled from an approved recipe.

    Only the recipe's author (or a moderator) may trigger this. One bite
    per recipe per author is enforced to prevent duplicate submissions.
    """
    recipe = get_object_or_404(
        Recipe.objects.select_related("author"),
        slug=slug,
        status=Recipe.Status.APPROVED,
        is_deleted=False,
    )

    if not (is_moderator(request.user) or user_can_manage_author(request.user, recipe.author)):
        raise Http404

    author = recipe.author

    # Prevent duplicate: one bite per recipe per author (excluding archived)
    existing = AmuseBouche.objects.filter(
        author=author,
        linked_recipe=recipe,
    ).exclude(status=AmuseBouche.Status.ARCHIVED).first()

    if existing:
        messages.info(request, "An Amuse-Bouche for this recipe already exists.")
        return redirect(existing.get_absolute_url())

    item = AmuseBouche.objects.create(
        author=author,
        title=recipe.title[:200],
        short_description=(recipe.short_description or "")[:500],
        content_type=AmuseBouche.ContentType.BEHIND_THE_DISH,
        linked_recipe=recipe,
        cover_image_alt=recipe.hero_image_alt_text or "",
        image_rights_status=recipe.image_rights_status,
        image_rights_note=recipe.image_rights_note or "",
        source_type=recipe.source_type,
        source_title=recipe.source_title or "",
        source_author=recipe.source_author or "",
        source_url=recipe.source_url or "",
        source_note=recipe.source_note or "",
        **_initial_status_fields(author, request.user),
    )

    track_event(
        request,
        "amuse_bouche_generated",
        object_type="amuse_bouche",
        object_id=item.pk,
        object_title=item.title,
    )

    if item.status == AmuseBouche.Status.APPROVED:
        messages.success(request, _created_message(item, ""))
        return redirect(item.get_absolute_url())

    messages.info(
        request,
        "Legal details copied from the original recipe. Please review and confirm them for this Amuse-Bouche.",
    )
    return redirect(
        reverse("amuse_bouche:edit", kwargs={"slug": item.slug}) + "?from_recipe=1"
    )


@require_POST
@login_required
def generate_from_article(request, slug):
    """Create an Amuse-Bouche pre-filled from an approved article.

    Only the article's author (or a moderator) may trigger this. One bite
    per article per author is enforced to prevent duplicate submissions.
    """
    article = get_object_or_404(
        Article.objects.select_related("author"),
        slug=slug,
        status=Article.Status.APPROVED,
        is_deleted=False,
    )

    if not (is_moderator(request.user) or user_can_manage_author(request.user, article.author)):
        raise Http404

    author = article.author

    # Prevent duplicate: one bite per article per author (excluding archived)
    existing = AmuseBouche.objects.filter(
        author=author,
        linked_article=article,
    ).exclude(status=AmuseBouche.Status.ARCHIVED).first()

    if existing:
        messages.info(request, "An Amuse-Bouche for this article already exists.")
        return redirect(existing.get_absolute_url())

    _article_source_map = {
        "adapted": AmuseBouche.SourceType.OTHER,
        "inspired": AmuseBouche.SourceType.OTHER,
    }
    source_type = _article_source_map.get(article.source_type, AmuseBouche.SourceType.ORIGINAL)

    item = AmuseBouche.objects.create(
        author=author,
        title=article.title[:200],
        short_description=(article.excerpt or "")[:500],
        content_type=AmuseBouche.ContentType.BEHIND_THE_DISH,
        linked_article=article,
        cover_image_alt=article.hero_image_alt_text or "",
        image_rights_status=article.image_rights_status,
        image_rights_note=article.image_rights_note or "",
        source_type=source_type,
        source_title=article.source_title or "",
        source_author=article.source_author or "",
        source_url=article.source_url or "",
        source_note=article.source_note or "",
        **_initial_status_fields(author, request.user),
    )

    track_event(
        request,
        "amuse_bouche_generated",
        object_type="amuse_bouche",
        object_id=item.pk,
        object_title=item.title,
    )

    if item.status == AmuseBouche.Status.APPROVED:
        messages.success(request, _created_message(item, ""))
        return redirect(item.get_absolute_url())

    messages.info(
        request,
        "Legal details copied from the original article. Please review and confirm them for this Amuse-Bouche.",
    )
    return redirect(
        reverse("amuse_bouche:edit", kwargs={"slug": item.slug}) + "?from_article=1"
    )


def comments_panel(request, slug):
    """AJAX endpoint: return comment panel HTML for a feed card."""
    _require_public_area_access(request)
    item = get_object_or_404(AmuseBouche, slug=slug, status=AmuseBouche.Status.APPROVED)
    if request.headers.get("X-AB-Fetch") != "1":
        return redirect(item.get_absolute_url())
    comments = []
    if item.allow_comments:
        comments = list(
            AmuseBoucheComment.objects.filter(amuse_bouche=item, is_deleted=False, parent__isnull=True)
            .select_related("user", "user__recipe_author_profile")
            .prefetch_related(
                Prefetch(
                    "replies",
                    queryset=AmuseBoucheComment.objects.filter(is_deleted=False)
                    .select_related("user", "user__recipe_author_profile"),
                    to_attr="active_replies",
                )
            )
            .order_by("created_at")
        )
    html = render_to_string(
        "amuse_bouche/comments_panel.html",
        {
            "item": item,
            "comments": comments,
            "user": request.user,
            "can_moderate": is_moderator(request.user),
        },
        request=request,
    )
    total = AmuseBoucheComment.objects.filter(amuse_bouche=item, is_deleted=False).count()
    return JsonResponse({"ok": True, "html": html, "count": total, "title": item.title})


@require_POST
@login_required
@ratelimit(key="user", rate="30/h", method="POST", block=False)
def submit_comment(request, slug):
    """Post a top-level comment or a reply on an Amuse-Bouche item."""
    _require_public_area_access(request)
    item = get_object_or_404(AmuseBouche, slug=slug, status=AmuseBouche.Status.APPROVED, allow_comments=True)
    is_fetch = request.headers.get("X-AB-Fetch") == "1"
    if getattr(request, "limited", False):
        if is_fetch:
            return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)
        messages.error(request, "Too many requests. Please slow down.")
        return redirect(item.get_absolute_url())
    body = request.POST.get("body", "").strip()
    if not body:
        if is_fetch:
            return JsonResponse({"ok": False, "error": "empty"}, status=400)
        messages.error(request, "Comment cannot be empty.")
        return redirect(item.get_absolute_url())
    if len(body) > 1000:
        if is_fetch:
            return JsonResponse({"ok": False, "error": "too_long"}, status=400)
        messages.error(request, "Comment is too long (maximum 1000 characters).")
        return redirect(item.get_absolute_url())
    # Optional parent for replies (only one level deep — no replies-to-replies)
    parent = None
    parent_id_raw = request.POST.get("parent_id", "").strip()
    if parent_id_raw:
        try:
            parent = AmuseBoucheComment.objects.get(
                pk=int(parent_id_raw),
                amuse_bouche=item,
                is_deleted=False,
                parent__isnull=True,  # only top-level comments can be replied to
            )
        except (AmuseBoucheComment.DoesNotExist, ValueError):
            if is_fetch:
                return JsonResponse({"ok": False, "error": "invalid_parent"}, status=400)
    comment = AmuseBoucheComment.objects.create(amuse_bouche=item, user=request.user, body=body, parent=parent)
    track_event(request, "ab_comment", object_type="amuse_bouche", object_id=item.pk, object_title=item.title)
    if is_fetch:
        comment_html = render_to_string(
            "amuse_bouche/comment_item.html",
            {
                "comment": comment,
                "user": request.user,
                "item": item,
                "can_moderate": is_moderator(request.user),
                "is_reply": parent is not None,
            },
            request=request,
        )
        total = AmuseBoucheComment.objects.filter(amuse_bouche=item, is_deleted=False).count()
        return JsonResponse({
            "ok": True,
            "comment_html": comment_html,
            "count": total,
            "parent_id": comment.parent_id,
        })
    messages.success(request, "Comment posted.")
    return redirect(item.get_absolute_url())


@require_POST
@login_required
def delete_comment(request, slug, comment_id):
    """Soft-delete a comment. Only the commenter or a moderator can delete."""
    item = get_object_or_404(AmuseBouche, slug=slug)
    comment = get_object_or_404(AmuseBoucheComment, pk=comment_id, amuse_bouche=item, is_deleted=False)
    if comment.user != request.user and not is_moderator(request.user):
        raise Http404
    comment.is_deleted = True
    comment.save(update_fields=["is_deleted"])
    is_fetch = request.headers.get("X-AB-Fetch") == "1"
    if is_fetch:
        total = AmuseBoucheComment.objects.filter(amuse_bouche=item, is_deleted=False).count()
        return JsonResponse({"ok": True, "comment_id": comment_id, "count": total})
    messages.success(request, "Comment removed.")
    return redirect(item.get_absolute_url())
