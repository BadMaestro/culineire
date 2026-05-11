import json

from django.conf import settings
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from collection.models import SavedArticle
from config.turnstile import verify_turnstile
from monitoring.tracker import track_event
from recipes.authoring import AuthorRequiredMixin, user_can_manage_author
from recipes.models import RecipeAuthor
from recipes.views import is_moderator
from .forms import ArticleAuthoringForm
from .models import Article, ArticleImage


class ArticleListView(ListView):
    model = Article
    template_name = "articles/article_list.html"
    context_object_name = "articles"
    paginate_by = 8

    def get_queryset(self):
        author_slug = (self.request.GET.get("author") or "").strip()
        selected_author = get_object_or_404(RecipeAuthor, slug=author_slug) if author_slug else None

        show_all = selected_author and is_moderator(self.request.user)

        queryset = Article.objects.select_related("author").order_by("-published")
        if not show_all:
            queryset = queryset.filter(status=Article.Status.APPROVED)
        if selected_author:
            queryset = queryset.filter(author=selected_author)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        author_slug = (self.request.GET.get("author") or "").strip()
        selected_author = None
        if author_slug:
            selected_author = get_object_or_404(RecipeAuthor, slug=author_slug)

        show_all = selected_author and is_moderator(self.request.user)

        recent_articles = None
        all_articles = None
        default_recent_articles = None
        all_articles_grid = None

        if selected_author:
            qs = Article.objects.select_related("author").filter(author=selected_author).order_by("-published")
            if not show_all:
                qs = qs.filter(status=Article.Status.APPROVED)
            all_articles = qs
            recent_articles = list(qs[:6])
        else:
            all_qs = (
                Article.objects.select_related("author")
                .filter(status=Article.Status.APPROVED)
                .order_by("-published")
            )
            default_recent_articles = list(all_qs[:6])
            all_articles_grid = list(all_qs[:50])

        context["selected_author"] = selected_author
        context["recent_articles"] = recent_articles
        context["all_articles"] = all_articles
        context["default_recent_articles"] = default_recent_articles
        context["all_articles_grid"] = all_articles_grid
        context["can_manage_selected_author"] = (
                is_moderator(self.request.user) or
                user_can_manage_author(self.request.user, selected_author)
        )
        return context


class ArticleCreateView(AuthorRequiredMixin, CreateView):
    model = Article
    form_class = ArticleAuthoringForm
    template_name = "authoring/article_form.html"

    def post(self, request, *args, **kwargs):
        token = request.POST.get("cf-turnstile-response", "")
        if not verify_turnstile(token, request.META.get("REMOTE_ADDR", "")):
            messages.error(request, "Security check failed. Please try again.")
            return redirect("articles:article_create")
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["author"] = self.author
        return kwargs

    def form_valid(self, form):
        article = form.save()
        self.object = article

        for i, img_file in enumerate(self.request.FILES.getlist("gallery_images"), start=1):
            ArticleImage.objects.create(article=article, image=img_file, sort_order=i)

        messages.success(self.request, "Article Created Successfully.")
        return redirect(article.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["turnstile_site_key"] = settings.TURNSTILE_SITE_KEY
        context["cancel_url"] = "/articles/"
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
        context["article_json_ld"] = mark_safe(json.dumps(_schema, ensure_ascii=False))
        context["is_saved"] = self.request.user.is_authenticated and SavedArticle.objects.filter(user=self.request.user, article=article).exists()
        context["collection_add_url"] = reverse("collection:add_article", kwargs={"slug": article.slug})
        context["collection_remove_url"] = reverse("collection:remove_article", kwargs={"slug": article.slug})
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
        kwargs["author"] = self.author
        return kwargs

    def form_valid(self, form):
        article = form.save()
        self.object = article

        existing_count = article.gallery_images.count()
        for i, img_file in enumerate(self.request.FILES.getlist("gallery_images"), start=existing_count + 1):
            ArticleImage.objects.create(article=article, image=img_file, sort_order=i)

        messages.success(self.request, "Article Updated Successfully.")
        if is_moderator(self.request.user):
            from django.urls import reverse
            return redirect(reverse("recipes:moderation_panel"))
        return redirect(article.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["form_mode"] = "edit"
        context["form_heading"] = "Edit Article"
        context["submit_label"] = "Save Changes"
        context["cancel_url"] = self.object.get_absolute_url() if self.object else "/articles/"
        return context


class ArticleDeleteView(AuthorRequiredMixin, DeleteView):
    model = Article
    template_name = "authoring/confirm_delete.html"
    context_object_name = "managed_object"
    success_url = "/articles/"

    def get_queryset(self):
        if is_moderator(self.request.user):
            return Article.objects.all()
        return Article.objects.filter(author=self.author)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, "Article Deleted Successfully.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["delete_title"] = "Delete Article"
        context["delete_intro"] = (
            f'You are about to delete "{self.object.title}". This action cannot be undone.'
        )
        context["delete_label"] = "Delete Article"
        context["cancel_url"] = self.object.get_absolute_url()
        return context
