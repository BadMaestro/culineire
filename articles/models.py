from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
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
    return f"{article_base_folder(instance)}/cover-{uuid4().hex[:12]}{extension}"


def article_gallery_upload_to(instance, filename: str) -> str:
    extension = Path(filename).suffix.lower() or ".jpg"
    sort_order = instance.sort_order or 1
    return f"{article_base_folder(instance.article)}/gallery/img{sort_order}-{uuid4().hex[:12]}{extension}"


class Article(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class ImageRightsStatus(models.TextChoices):
        OWN = "own", "My own photo"
        AI_GENERATED = "ai_generated", "AI generated image"
        LICENSED = "licensed", "Licensed (CC, stock, written permission)"
        PUBLIC_DOMAIN = "public_domain", "Public domain"
        NOT_APPLICABLE = "not_applicable", "No image uploaded"

    class SourceType(models.TextChoices):
        ORIGINAL = "original", "Original writing"
        ADAPTED = "adapted", "Adapted from a source"
        INSPIRED = "inspired", "Inspired by a source"

    title = models.CharField("Title", max_length=200)
    slug = models.SlugField("Slug", max_length=220, unique=True, db_index=True)
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
    hero_image_alt_text = models.CharField(
        "Article image alt text",
        max_length=255,
        blank=True,
        help_text="Describe the article image for accessibility and search indexing.",
    )

    status = models.CharField(
        "Status",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
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

    image_rights_status = models.CharField(
        "Image rights",
        max_length=20,
        choices=ImageRightsStatus.choices,
        default=ImageRightsStatus.OWN,
    )
    image_rights_note = models.CharField(
        "Image rights note",
        max_length=255,
        blank=True,
        help_text="Credit line or permission reference if any.",
    )

    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.ORIGINAL,
    )
    source_title = models.CharField(max_length=255, blank=True)
    source_author = models.CharField(max_length=255, blank=True)
    source_url = models.URLField(blank=True)
    source_note = models.CharField(max_length=255, blank=True)

    confirmed_own_work = models.BooleanField(default=False)
    confirmed_image_rights = models.BooleanField(default=False)
    confirmed_rules = models.BooleanField(default=False)
    confirmation_timestamp = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_articles",
        editable=False,
    )

    moderation_note = models.TextField(blank=True, default="")
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_articles",
    )
    moderated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published"]
        verbose_name = "Article"
        verbose_name_plural = "Articles"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("articles:article_detail", args=[self.slug])

    @property
    def card_image(self):
        if self.hero_image:
            return self.hero_image

        prefetched_gallery = getattr(self, "active_card_gallery_images", None)
        if prefetched_gallery is not None:
            return prefetched_gallery[0].image if prefetched_gallery else None

        first_gallery_image = self.gallery_images.filter(is_active=True).order_by("sort_order", "id").first()
        return first_gallery_image.image if first_gallery_image else None

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

    def clean(self):
        super().clean()
        if (
            self.article_id
            and self.is_active
            and self.article.image_rights_status == Article.ImageRightsStatus.NOT_APPLICABLE
        ):
            raise ValidationError(
                {
                    "image": (
                        "Choose the correct image rights status before attaching "
                        "active article gallery images."
                    )
                }
            )
