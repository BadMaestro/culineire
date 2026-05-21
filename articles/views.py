import json
import logging

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, Prefetch, Q
from django.http import Http404
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from collection.models import SavedArticle
from config.turnstile import verify_turnstile
from monitoring.tracker import track_event
from recipes.authoring import AuthorRequiredMixin, user_can_manage_author
from recipes.models import RecipeAuthor
from recipes.validators import validate_image_upload
from accounts.views import is_moderator
from .forms import ArticleAuthoringForm
from .models import Article, ArticleImage

logger = logging.getLogger(__name__)


ARTICLE_CARD_GALLERY_PREFETCH = Prefetch(
    "gallery_images",
    queryset=ArticleImage.objects.filter(is_active=True).order_by("sort_order", "id"),
    to_attr="active_card_gallery_images",
)


def _reading_time_minutes(text):
    return max(1, round(len(text.split()) / 200))


def _json_ld(data):
    value = json.dumps(data, ensure_ascii=False)
    value = value.replace("&", "\\u0026").replace("<", "\\u003C").replace(">", "\\u003E")
    return mark_safe(value)


def _validate_gallery_uploads(form, uploaded_files):
    is_valid = True
    if (
        uploaded_files
        and form.cleaned_data.get("image_rights_status") == Article.ImageRightsStatus.NOT_APPLICABLE
    ):
        form.add_error(
            "image_rights_status",
            "Choose the correct image rights status when gallery images are attached.",
        )
        is_valid = False

    for uploaded_file in uploaded_files:
        try:
            validate_image_upload(uploaded_file)
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, f"Gallery image {uploaded_file.name}: {message}")
            is_valid = False
    return is_valid


class ArticleListView(ListView):
    model = Article
    template_name = "articles/article_list.html"
    context_object_name = "articles"
    paginate_by = 8

    def _selected_author(self):
        author_slug = (self.request.GET.get("author") or "").strip()
        return get_object_or_404(RecipeAuthor, slug=author_slug) if author_slug else None

    def _can_manage_selected_author(self, selected_author):
        return bool(
            selected_author and (
                is_moderator(self.request.user) or
                user_can_manage_author(self.request.user, selected_author)
            )
        )

    def get_queryset(self):
        selected_author = self._selected_author()
        show_all = self._can_manage_selected_author(selected_author)

        queryset = (
            Article.objects.select_related("author")
            .prefetch_related(ARTICLE_CARD_GALLERY_PREFETCH)
            .order_by("-published")
        )
        if not show_all:
            queryset = queryset.filter(status=Article.Status.APPROVED)
        if selected_author:
            queryset = queryset.filter(author=selected_author)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_author = self._selected_author()
        can_manage_selected_author = self._can_manage_selected_author(selected_author)

        recent_articles = None
        all_articles = None
        default_recent_articles = None
        all_articles_grid = None

        if selected_author:
            qs = (
                Article.objects.select_related("author")
                .prefetch_related(ARTICLE_CARD_GALLERY_PREFETCH)
                .filter(author=selected_author)
                .order_by("-published")
            )
            if not can_manage_selected_author:
                qs = qs.filter(status=Article.Status.APPROVED)
            all_articles = qs
            recent_articles = list(qs[:6])
        else:
            all_qs = (
                Article.objects.select_related("author")
                .prefetch_related(ARTICLE_CARD_GALLERY_PREFETCH)
                .filter(status=Article.Status.APPROVED)
                .order_by("-published")
            )
            default_recent_articles = list(all_qs[:6])
            all_articles_grid = list(all_qs)

        context["selected_author"] = selected_author
        context["recent_articles"] = recent_articles
        context["all_articles"] = all_articles
        context["default_recent_articles"] = default_recent_articles
        context["all_articles_grid"] = all_articles_grid
        context["can_manage_selected_author"] = can_manage_selected_author
        return context


class ArticleCreateView(AuthorRequiredMixin, CreateView):
    model = Article
    form_class = ArticleAuthoringForm
    template_name = "authoring/article_form.html"

    def post(self, request, *args, **kwargs):
        token = request.POST.get("cf-turnstile-response", "")
        if not verify_turnstile(token, request.META.get("REMOTE_ADDR", "")):
            form = self.get_form()
            form.add_error(None, "Security check failed. Please try again.")
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["author"] = self.author
        return kwargs

    def form_valid(self, form):
        gallery_images = self.request.FILES.getlist("gallery_images")
        if not _validate_gallery_uploads(form, gallery_images):
            return self.form_invalid(form)

        with transaction.atomic():
            article = form.save(confirmed_by=self.request.user)
            self.object = article

            if is_moderator(self.request.user):
                article.status = Article.Status.APPROVED
                article.save(update_fields=["status"])

            for i, img_file in enumerate(gallery_images, start=1):
                ArticleImage.objects.create(article=article, image=img_file, sort_order=i)

        messages.success(self.request, "Article Created Successfully.")
        return redirect(article.get_absolute_url())

    def form_invalid(self, form):
        logger.warning(
            "Article create form invalid for user_id=%s errors=%s",
            getattr(self.request.user, "id", None),
            form.errors.as_json(),
        )
        messages.error(self.request, "Please fix the highlighted fields and try again.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["turnstile_site_key"] = settings.TURNSTILE_SITE_KEY
        context["cancel_url"] = reverse("articles:article_list")
        return context


class ArticleDetailView(DetailView):
    model = Article
    template_name = "articles/article_detail.html"
    context_object_name = "article"

    _GALLERY_PREFETCH = Prefetch(
        "gallery_images",
        queryset=ArticleImage.objects.filter(is_active=True).order_by("sort_order", "id"),
    )

    def get_queryset(self):
        qs = Article.objects.select_related("author", "related_recipe").prefetch_related(
            self._GALLERY_PREFETCH
        )
        if is_moderator(self.request.user):
            return qs

        viewer_author = getattr(self.request.user, "recipe_author_profile", None)
        if viewer_author:
            return qs.filter(Q(status=Article.Status.APPROVED) | Q(author=viewer_author))

        return qs.filter(status=Article.Status.APPROVED)

    @staticmethod
    def _image_to_gallery_item(image_field, alt, caption=""):
        return {
            "src": image_field.url,
            "alt": alt,
            "caption": caption or "",
            "width": getattr(image_field, "width", None),
            "height": getattr(image_field, "height", None),
        }

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        track_event(
            request,
            "article_view",
            object_type="article",
            object_id=self.object.pk,
            object_title=self.object.title,
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object

        active_gallery_images = list(article.gallery_images.all())

        if active_gallery_images:
            gallery_items = [
                self._image_to_gallery_item(
                    image.image,
                    alt=image.alt_text or article.title,
                    caption=image.caption or "",
                )
                for image in active_gallery_images
            ]
        elif article.hero_image:
            gallery_items = [
                self._image_to_gallery_item(
                    article.hero_image,
                    alt=article.title,
                )
            ]
        else:
            gallery_items = []

        context["article_hero_image"] = article.card_image
        context["gallery_items"] = gallery_items
        context["has_gallery"] = len(gallery_items) > 1
        context["can_manage_article"] = (
                is_moderator(self.request.user) or
                user_can_manage_author(self.request.user, article.author)
        )
        context["can_moderate_bar"] = (
                is_moderator(self.request.user) and
                article.status != Article.Status.APPROVED
        )
        context["can_collect_article"] = (
                self.request.user.is_authenticated and
                article.status == Article.Status.APPROVED
        )

        _schema: dict = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": article.title,
            "description": article.excerpt or f"An article about {article.title}.",
            "author": {"@type": "Person", "name": article.author.name} if article.author else {"@type": "Organization", "name": "CulinEire"},
            "datePublished": article.published.strftime("%Y-%m-%d") if article.published else "",
            "url": self.request.build_absolute_uri(),
            "publisher": {
                "@type": "Organization",
                "name": "CulinEire",
                "logo": {"@type": "ImageObject", "url": self.request.build_absolute_uri("/static/images/logo.png")},
            },
        }
        if gallery_items:
            _schema["image"] = self.request.build_absolute_uri(gallery_items[0]["src"])
        context["article_json_ld"] = _json_ld(_schema)
        context["is_saved"] = context["can_collect_article"] and SavedArticle.objects.filter(user=self.request.user, article=article).exists()
        context["collection_add_url"] = reverse("collection:add_article", kwargs={"slug": article.slug})
        context["collection_remove_url"] = reverse("collection:remove_article", kwargs={"slug": article.slug})
        context["reading_time"] = _reading_time_minutes(article.body or "")
        return context


class ArticleUpdateView(AuthorRequiredMixin, UpdateView):
    model = Article
    form_class = ArticleAuthoringForm
    template_name = "authoring/article_form.html"
    context_object_name = "article"

    def get_queryset(self):
        if is_moderator(self.request.user):
            return Article.objects.all()
        return Article.objects.filter(author=self.author)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def form_valid(self, form):
        gallery_images = self.request.FILES.getlist("gallery_images")
        if not _validate_gallery_uploads(form, gallery_images):
            return self.form_invalid(form)

        with transaction.atomic():
            was_approved = self.object.status == Article.Status.APPROVED
            article = form.save(commit=False, confirmed_by=self.request.user)
            if not is_moderator(self.request.user):
                article.status = Article.Status.PENDING
            article.save()
            form.save_m2m()
            self.object = article

            max_sort_order = article.gallery_images.aggregate(max_sort_order=Max("sort_order"))["max_sort_order"] or 0
            for i, img_file in enumerate(gallery_images, start=max_sort_order + 1):
                ArticleImage.objects.create(article=article, image=img_file, sort_order=i)

        if was_approved and not is_moderator(self.request.user):
            messages.success(
                self.request,
                "Article updated and sent back to review before it goes live again.",
            )
        else:
            messages.success(self.request, "Article Updated Successfully.")
        return redirect(article.get_absolute_url())

    def form_invalid(self, form):
        logger.warning(
            "Article update form invalid for article_id=%s user_id=%s errors=%s",
            getattr(self.object, "id", None),
            getattr(self.request.user, "id", None),
            form.errors.as_json(),
        )
        messages.error(self.request, "Please fix the highlighted fields and try again.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.object.author if self.object else self.author
        context["form_mode"] = "edit"
        context["form_heading"] = "Edit Article"
        context["submit_label"] = "Save Changes"
        context["cancel_url"] = self.object.get_absolute_url() if self.object else reverse("articles:article_list")
        context["turnstile_site_key"] = ""
        context["will_return_to_review"] = (
            bool(self.object)
            and self.object.status == Article.Status.APPROVED
            and not is_moderator(self.request.user)
        )
        if self.object:
            context["existing_gallery_images"] = list(
                self.object.gallery_images.filter(is_active=True).order_by("sort_order", "id")
            )
        return context


class ArticleDeleteView(AuthorRequiredMixin, DeleteView):
    model = Article
    template_name = "authoring/confirm_delete.html"
    context_object_name = "managed_object"
    success_url = reverse_lazy("articles:article_list")

    def get_queryset(self):
        if is_moderator(self.request.user):
            return Article.objects.all()
        return Article.objects.filter(author=self.author)

    def form_valid(self, form):
        messages.success(self.request, "Article Deleted Successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.object.author
        context["delete_title"] = "Delete Article"
        context["delete_intro"] = (
            f'You are about to delete "{self.object.title}". This action cannot be undone.'
        )
        context["delete_label"] = "Delete Article"
        context["cancel_url"] = self.object.get_absolute_url()
        return context


# ── Moderation ────────────────────────────────────────────────────────────────

@require_POST
def delete_article_hero_image(request, slug):
    article = get_object_or_404(Article.objects.select_related("author"), slug=slug)

    if not (is_moderator(request.user) or user_can_manage_author(request.user, article.author)):
        raise Http404

    if article.hero_image:
        article.hero_image.delete(save=False)
        article.hero_image = None
        article.save(update_fields=["hero_image"])
        messages.success(request, "Article image deleted.")
    else:
        messages.info(request, "Article image was already empty.")
    return redirect(reverse("articles:article_edit", kwargs={"slug": article.slug}))


@require_POST
def delete_article_gallery_image(request, image_id):
    image = get_object_or_404(
        ArticleImage.objects.select_related("article", "article__author"),
        pk=image_id,
    )
    article = image.article

    if not (is_moderator(request.user) or user_can_manage_author(request.user, article.author)):
        raise Http404

    image.delete()
    messages.success(request, "Gallery image deleted.")
    return redirect(reverse("articles:article_edit", kwargs={"slug": article.slug}))


@require_POST
def moderate_article(request, slug):
    if not is_moderator(request.user):
        raise Http404
    article = get_object_or_404(Article, slug=slug)
    action = request.POST.get("action")

    if action == "approve":
        article.status = Article.Status.APPROVED
        article.moderation_note = ""
        article.moderated_by = request.user
        article.moderated_at = timezone.now()
        article.save(update_fields=["status", "moderation_note", "moderated_by", "moderated_at"])
        messages.success(request, f'"{article.title}" approved and is now live.')
    elif action == "reject":
        note = request.POST.get("moderation_note", "").strip()
        if not note:
            messages.error(request, "A rejection note is required. Please explain what needs to be corrected.")
            return redirect(article.get_absolute_url())
        article.status = Article.Status.REJECTED
        article.moderation_note = note
        article.moderated_by = request.user
        article.moderated_at = timezone.now()
        article.save(update_fields=["status", "moderation_note", "moderated_by", "moderated_at"])
        messages.warning(request, f'"{article.title}" rejected.')
    elif action == "delete":
        title = article.title
        article.delete()
        messages.success(request, f'"{title}" permanently deleted.')
    else:
        raise Http404

    if action != "delete":
        try:
            return redirect(article.get_absolute_url())
        except (AttributeError, TypeError, ValueError):
            pass
    return redirect("recipes:moderation_panel")
