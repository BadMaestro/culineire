from __future__ import annotations

from pathlib import Path

from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from recipes.models import Recipe, RecipeAuthor
from recipes.validators import validate_image_upload


MAX_MEDIA_FOLDER_SEGMENT_LENGTH = 80


def _slug_folder_segment(value: str, fallback: str, max_length: int = MAX_MEDIA_FOLDER_SEGMENT_LENGTH) -> str:
    slug = slugify((value or "").strip())[:max_length].strip("-")
    return slug or fallback


def unique_media_folder_for_article(article) -> str:
    if getattr(article, "media_folder", None):
        return article.media_folder

    base_name = _slug_folder_segment(getattr(article, "title", ""), "article")

    existing_names = set(
        Article.objects.exclude(pk=article.pk)
        .exclude(media_folder="")
        .values_list("media_folder", flat=True)
    )

    if base_name not in existing_names:
        return base_name

    counter = 2
    while True:
        candidate = f"{base_name} {counter}"
        if candidate not in existing_names:
            return candidate
        counter += 1


def article_base_folder(article) -> str:
    article_folder = unique_media_folder_for_article(article)
    return f"articles/{article_folder}"


def article_cover_upload_to(instance, filename: str) -> str:
    extension = Path(filename).suffix.lower() or ".jpg"
    return f"{article_base_folder(instance)}/cover{extension}"


def article_gallery_upload_to(instance, filename: str) -> str:
    extension = Path(filename).suffix.lower() or ".jpg"
    sort_order = instance.sort_order or 1
    return f"{article_base_folder(instance.article)}/gallery/img{sort_order}{extension}"


class Article(models.Model):
    title = models.CharField("Title", max_length=200)
    slug = models.SlugField("Slug", unique=True)
    media_folder = models.CharField(max_length=255, blank=True, editable=False, db_index=True)

    author = models.ForeignKey(
        RecipeAuthor,
        on_delete=models.PROTECT,
        related_name="articles",
        verbose_name="Author",
    )

    excerpt = models.TextField("Excerpt", blank=True)
    body = models.TextField("Body")

    hero_image = models.ImageField(
        "Preview image",
        upload_to=article_cover_upload_to,
        blank=True,
        null=True,
        validators=[validate_image_upload],
    )

    published = models.DateField("Published")
    related_recipe = models.ForeignKey(
        Recipe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
        verbose_name="Related recipe",
    )

    class Meta:
        ordering = ["-published"]
        verbose_name = "Article"
        verbose_name_plural = "Articles"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("articles:article_detail", args=[self.slug])

    def save(self, *args, **kwargs):
        if not self.media_folder:
            self.media_folder = unique_media_folder_for_article(self)
        super().save(*args, **kwargs)


class ArticleImage(models.Model):
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )
    image = models.ImageField(
        upload_to=article_gallery_upload_to,
        validators=[validate_image_upload],
    )
    alt_text = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Article gallery image"
        verbose_name_plural = "Article gallery images"

    def __str__(self):
        return f"{self.article.title} — image {self.id}"
