from django.db.models import Prefetch
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from recipes.authoring import AuthorRequiredMixin, user_can_manage_author
from recipes.models import RecipeAuthor
from .forms import ArticleAuthoringForm
from .models import Article, ArticleImage


class ArticleListView(ListView):
    model = Article
    template_name = "articles/article_list.html"
    context_object_name = "articles"
    paginate_by = 8

    def get_queryset(self):
        queryset = Article.objects.select_related("author").order_by("-published")
        author_slug = (self.request.GET.get("author") or "").strip()
        if author_slug:
            queryset = queryset.filter(
                author=get_object_or_404(RecipeAuthor, slug=author_slug)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        author_slug = (self.request.GET.get("author") or "").strip()
        selected_author = None
        if author_slug:
            selected_author = get_object_or_404(RecipeAuthor, slug=author_slug)

        recent_articles = None
        all_articles = None
        if selected_author:
            all_articles = Article.objects.select_related("author").filter(
                author=selected_author
            ).order_by("-published")
            recent_articles = list(all_articles[:6])

        context["selected_author"] = selected_author
        context["recent_articles"] = recent_articles
        context["all_articles"] = all_articles
        context["can_manage_selected_author"] = user_can_manage_author(
            self.request.user, selected_author
        )
        return context


class ArticleCreateView(AuthorRequiredMixin, CreateView):
    model = Article
    form_class = ArticleAuthoringForm
    template_name = "authoring/article_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["author"] = self.author
        return kwargs

    def form_valid(self, form):
        article = form.save()
        self.object = article
        messages.success(self.request, "Article Created Successfully.")
        return redirect(article.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
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
        return Article.objects.select_related("author", "related_recipe").prefetch_related(
            self._GALLERY_PREFETCH
        )

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
        context["can_manage_article"] = user_can_manage_author(
            self.request.user, article.author
        )
        return context


class ArticleUpdateView(AuthorRequiredMixin, UpdateView):
    model = Article
    form_class = ArticleAuthoringForm
    template_name = "authoring/article_form.html"
    context_object_name = "article"

    def get_queryset(self):
        return Article.objects.filter(author=self.author)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["author"] = self.author
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Article Updated Successfully.")
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["form_mode"] = "edit"
        context["form_heading"] = "Edit Article"
        context["form_intro"] = (
            "Tighten the story, update the linked recipe and keep your article polished."
        )
        context["submit_label"] = "Save Changes"
        return context


class ArticleDeleteView(AuthorRequiredMixin, DeleteView):
    model = Article
    template_name = "authoring/confirm_delete.html"
    context_object_name = "managed_object"
    success_url = "/articles/"

    def get_queryset(self):
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
