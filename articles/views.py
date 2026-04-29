from django.db.models import Prefetch
from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import CreateView, DetailView, ListView

from recipes.authoring import AuthorRequiredMixin
from .forms import ArticleAuthoringForm
from .models import Article, ArticleImage


class ArticleListView(ListView):
    model = Article
    template_name = "articles/article_list.html"
    context_object_name = "articles"
    paginate_by = 8

    def get_queryset(self):
        return Article.objects.select_related("author").order_by("-published")


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
        return context
