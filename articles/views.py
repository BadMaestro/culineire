from django.conf import settings
from django.contrib import messages
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from config.turnstile import verify_turnstile
from recipes.authoring import AuthorRequiredMixin, user_can_manage_author
from recipes.models import RecipeAuthor
from recipes.views import _is_moderator
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

        show_all = selected_author and _is_moderator(self.request.user)

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

        show_all = selected_author and _is_moderator(self.request.user)

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
                _is_moderator(self.request.user) or
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
        queryset=ArticleImage.objects.filter(is_active=True).order_by("-sort_order", "-id"),
    )

    def get_queryset(self):
        qs = Article.objects.select_related("author", "related_recipe").prefetch_related(
            self._GALLERY_PREFETCH
        )
        if _is_moderator(self.request.user):
            return qs
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
                _is_moderator(self.request.user) or
                user_can_manage_author(self.request.user, article.author)
        )
        context["can_moderate_bar"] = (
                _is_moderator(self.request.user) and
                article.status != Article.Status.APPROVED
        )
        return context


class ArticleUpdateView(AuthorRequiredMixin, UpdateView):
    model = Article
    form_class = ArticleAuthoringForm
    template_name = "authoring/article_form.html"
    context_object_name = "article"

    def get_queryset(self):
        if _is_moderator(self.request.user):
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
        if _is_moderator(self.request.user):
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
        if _is_moderator(self.request.user):
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
