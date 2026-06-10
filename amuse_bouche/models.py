from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

logger = logging.getLogger(__name__)

from collection.models import ContentReaction, SavedContent
from recipes.models import Recipe, RecipeAuthor, safe_author_folder, safe_media_segment
from recipes.validators import validate_image_upload
from articles.models import Article


def unique_media_folder_for_amuse_bouche(item) -> str:
    if getattr(item, "media_folder", None):
        return item.media_folder

    base_name = safe_media_segment(getattr(item, "title", ""), "amuse-bouche")
    author = getattr(item, "author", None)
    existing = AmuseBouche.objects.exclude(pk=item.pk)
    existing = existing.filter(author=author) if author else existing.filter(author__isnull=True)
    existing_names = set(existing.exclude(media_folder="").values_list("media_folder", flat=True))

    if base_name not in existing_names:
        return base_name

    counter = 2
    while True:
        candidate = f"{base_name} {counter}"
        if candidate not in existing_names:
            return candidate
        counter += 1


def amuse_bouche_base_folder(item) -> str:
    author_folder = safe_author_folder(getattr(item, "author", None))
    item_folder = unique_media_folder_for_amuse_bouche(item)
    return f"amuse-bouche/{author_folder}/{item_folder}"


def amuse_bouche_cover_upload_to(instance, filename: str) -> str:
    extension = Path(filename).suffix.lower() or ".jpg"
    return f"{amuse_bouche_base_folder(instance)}/cover-{uuid4().hex[:12]}{extension}"


def amuse_bouche_gallery_upload_to(instance, filename: str) -> str:
    extension = Path(filename).suffix.lower() or ".jpg"
    sort_order = instance.sort_order or 1
    return f"{amuse_bouche_base_folder(instance.amuse_bouche)}/gallery/img{sort_order}-{uuid4().hex[:12]}{extension}"


class AmuseBouche(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        NEEDS_CHANGES = "NEEDS_CHANGES", "Needs changes"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    class ImageRightsStatus(models.TextChoices):
        OWN = "own", "My own photo"
        AI_GENERATED = "ai_generated", "AI generated image"
        LICENSED = "licensed", "Licensed (CC, stock, written permission)"
        PUBLIC_DOMAIN = "public_domain", "Public domain"
        NOT_APPLICABLE = "not_applicable", "No image uploaded"

    class SourceType(models.TextChoices):
        ORIGINAL = "original", "Original"
        AI_ASSISTED = "ai_assisted", "AI assisted"
        FAMILY = "family", "Family recipe"
        COOKBOOK = "cookbook", "Cookbook"
        WEBSITE = "website", "Website"
        RESTAURANT = "restaurant", "Restaurant"
        OTHER = "other", "Other"

    class ContentType(models.TextChoices):
        MINI_RECIPE = "mini_recipe", "Mini Recipe"
        SNACK = "snack", "Snack"
        SAUCE = "sauce", "Sauce"
        COCKTAIL = "cocktail", "Cocktail"
        QUICK_TIP = "quick_tip", "Quick Tip"
        PLATING_IDEA = "plating_idea", "Plating Idea"
        LEFTOVER_IDEA = "leftover_idea", "Leftover Idea"
        IRISH_BITE = "irish_bite", "Irish Bite"
        CHEF_TRICK = "chef_trick", "Chef Trick"
        BEHIND_THE_DISH = "behind_the_dish", "Behind The Dish"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, db_index=True, blank=True)
    media_folder = models.CharField(max_length=255, blank=True, editable=False, db_index=True)
    author = models.ForeignKey(
        RecipeAuthor,
        on_delete=models.PROTECT,
        related_name="amuse_bouche_items",
    )
    short_description = models.TextField(blank=True)
    content_type = models.CharField(
        max_length=40,
        choices=ContentType.choices,
        default=ContentType.IRISH_BITE,
        db_index=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    cover_image = models.ImageField(
        upload_to=amuse_bouche_cover_upload_to,
        blank=True,
        null=True,
        validators=[validate_image_upload],
    )
    cover_image_alt = models.CharField(max_length=255, blank=True)
    linked_recipe = models.ForeignKey(
        Recipe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="amuse_bouche_items",
    )
    linked_article = models.ForeignKey(
        Article,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="amuse_bouche_items",
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_announcement = models.BooleanField(default=False, db_index=True)
    allow_comments = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0)
    moderation_note = models.TextField(blank=True, default="")
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_amuse_bouche_items",
    )
    moderated_at = models.DateTimeField(null=True, blank=True)

    image_rights_status = models.CharField(
        "Image rights",
        max_length=20,
        choices=ImageRightsStatus.choices,
        default=ImageRightsStatus.NOT_APPLICABLE,
    )
    image_rights_note = models.CharField(
        "Image rights note",
        max_length=255,
        blank=True,
        help_text="Credit line or permission reference if applicable.",
    )

    source_type = models.CharField(
        "Source type",
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.ORIGINAL,
    )
    source_title = models.CharField("Source title", max_length=255, blank=True)
    source_author = models.CharField("Source author", max_length=255, blank=True)
    source_url = models.URLField("Source URL", blank=True)
    source_note = models.TextField("Source note", blank=True)

    confirmed_own_work = models.BooleanField(
        "Confirmed: original or properly credited work",
        default=False,
    )
    confirmed_image_rights = models.BooleanField(
        "Confirmed: image rights",
        default=False,
    )
    confirmed_rules = models.BooleanField(
        "Confirmed: content publishing rules",
        default=False,
    )
    confirmation_timestamp = models.DateTimeField(
        "Confirmed at",
        null=True,
        blank=True,
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_amuse_bouche_items",
        verbose_name="Confirmed by",
        editable=False,
    )

    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.CharField(max_length=255, blank=True)
    emoji_description = models.TextField(
        blank=True,
        help_text="Emoji-decorated description shown in the feed card. Generate via admin action or management command; edit freely.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    saves = GenericRelation(SavedContent, related_query_name="amuse_bouche_items")
    reactions = GenericRelation(ContentReaction, related_query_name="amuse_bouche_items")

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["content_type", "status"]),
            models.Index(fields=["is_featured", "status"]),
        ]
        verbose_name = "Amuse-Bouche"
        verbose_name_plural = "Amuse-Bouche"

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self):
        return reverse("amuse_bouche:detail", kwargs={"slug": self.slug})

    @property
    def author_status_label(self) -> str:
        return {
            self.Status.DRAFT: "Draft",
            self.Status.PENDING: "Waiting for review",
            self.Status.APPROVED: "Published",
            self.Status.NEEDS_CHANGES: "Needs changes",
            self.Status.REJECTED: "Rejected",
            self.Status.ARCHIVED: "Archived",
        }.get(self.status, self.get_status_display())

    @property
    def public_description(self) -> str:
        return self.seo_description or self.short_description

    @property
    def card_image(self):
        if self.cover_image:
            return self.cover_image
        # Use prefetched gallery images (to_attr="active_gallery_images") when
        # available — avoids an N+1 query on feed and home-page list views.
        # Falls back to a direct DB hit on detail-page or ad-hoc access.
        gallery = getattr(self, "active_gallery_images", None)
        if gallery is None:
            gallery = list(
                self.gallery_images.filter(is_active=True).order_by("sort_order", "id")[:1]
            )
        first = gallery[0] if gallery else None
        if first:
            return first.image
        # Fall back to linked recipe hero image so generated bites look good immediately
        if self.linked_recipe_id and self.linked_recipe.hero_image:
            return self.linked_recipe.hero_image
        if self.linked_article_id and self.linked_article.card_image:
            return self.linked_article.card_image
        return None

    def generate_unique_slug(self) -> str:
        base_slug = slugify(self.title)[:200] or "amuse-bouche"
        slug = base_slug
        counter = 2
        while AmuseBouche.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            suffix = f"-{counter}"
            slug = f"{base_slug[:220 - len(suffix)]}{suffix}"
            counter += 1
        return slug

    def generate_emoji_description(self) -> None:
        """
        Call Anthropic API via raw urllib to produce an emoji-decorated description. Fails silently.

        This is an opt-in, explicit call only — never invoked automatically during save().
        Call it from management commands, admin actions, or generation workflows, then save separately.
        """
        import json
        from urllib.request import Request, urlopen

        try:
            api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
            model = getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6")
            if not api_key:
                return
            source_text = self.short_description or self.title
            payload = {
                "model": model,
                "max_tokens": 120,
                "messages": [{
                    "role": "user",
                    "content": (
                        "You are a warm, playful food writer for an Irish culinary site. "
                        "Rewrite the following culinary bite in one or two short sentences, "
                        "weaving in relevant food and nature emojis naturally. "
                        "Keep the tone appetising, friendly and concise. "
                        "Output only the rewritten text, no title, no quotes.\n\n"
                        f"Title: {self.title}\n"
                        f"Description: {source_text}"
                    ),
                }],
            }
            request = Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "content-type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
            self.emoji_description = body["content"][0]["text"].strip()
        except Exception as exc:
            logger.warning("AmuseBouche.generate_emoji_description failed: %s", exc)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug()
        if not self.media_folder:
            self.media_folder = unique_media_folder_for_amuse_bouche(self)
        if self.status == self.Status.APPROVED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class AmuseBoucheGalleryImage(models.Model):
    amuse_bouche = models.ForeignKey(
        AmuseBouche,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )
    image = models.ImageField(upload_to=amuse_bouche_gallery_upload_to, validators=[validate_image_upload])
    alt_text = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Amuse-Bouche gallery image"
        verbose_name_plural = "Amuse-Bouche gallery images"

    def __str__(self) -> str:
        return f"{self.amuse_bouche.title} - image {self.id}"


class AmuseBoucheComment(models.Model):
    """A user comment on an Amuse-Bouche item.

    Only available when the item has allow_comments=True and the commenter
    has access to the Amuse-Bouche public area.
    """

    amuse_bouche = models.ForeignKey(
        AmuseBouche,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ab_comments",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["amuse_bouche", "is_deleted", "created_at"]),
        ]
        verbose_name = "Amuse-Bouche comment"
        verbose_name_plural = "Amuse-Bouche comments"

    def __str__(self) -> str:
        return f"{self.user} on {self.amuse_bouche.title[:40]}"
