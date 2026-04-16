from django.db.models import Prefetch
from django.views.generic import DetailView, ListView

from .models import Article, ArticleImage


class ArticleListView(ListView):
    model = Article
    template_name = "articles/article_list.html"
    context_object_name = "articles"
    paginate_by = 8

    def get_queryset(self):
        return (
            Article.objects.select_related("author", "related_recipe")
            .order_by("-published")
        )


class ArticleDetailView(DetailView):
    model = Article
    template_name = "articles/article_detail.html"
    context_object_name = "article"

    def get_queryset(self):
        return (
            Article.objects.select_related("author", "related_recipe").prefetch_related(
                Prefetch(
                    "gallery_images",
                    queryset=ArticleImage.objects.filter(is_active=True).order_by("sort_order", "id"),
                )
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object

        gallery_items = []
        active_gallery_images = list(article.gallery_images.all())

        if active_gallery_images:
            for image in active_gallery_images:
                gallery_items.append(
                    {
                        "media_type": "image",
                        "src": image.image.url,
                        "alt": image.alt_text or article.title,
                    }
                )
        elif article.hero_image:
            gallery_items.append(
                {
                    "media_type": "image",
                    "src": article.hero_image.url,
                    "alt": article.title,
                }
            )

        context["gallery_items"] = gallery_items
        return context