from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import Article, ArticleImage


class ArticleAdminForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = "__all__"
        labels = {
            "hero_image": "Preview image",
            "excerpt": "Short description",
            "body": "Article content",
        }
        help_texts = {
            "author": "Required. Every article must belong to an author.",
            "hero_image": "Main image used on article cards and at the top of the article page.",
            "excerpt": "Short introductory text shown on the card and under the article title.",
            "related_recipe": "Optional. Link this article to a recipe if one exists.",
        }


class ArticleImageInline(admin.TabularInline):
    model = ArticleImage
    extra = 1
    fields = (
        "image_preview",
        "image",
        "alt_text",
        "caption",
        "sort_order",
        "is_active",
    )
    readonly_fields = ("image_preview",)
    ordering = ("sort_order", "id")
    verbose_name = "Gallery item"
    verbose_name_plural = "Gallery items"

    def image_preview(self, obj):
        if obj and obj.image:
            return format_html(
                '<img src="{}" alt="Gallery preview" style="width: 120px; height: 90px; object-fit: cover; border-radius: 10px; border: 1px solid #d8d2c8;" />',
                obj.image.url,
            )
        return "No image"

    image_preview.short_description = "Preview"


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleAdminForm
    list_display = (
        "title",
        "article_preview_small",
        "author",
        "published",
        "related_recipe",
    )
    list_filter = (
        "published",
        "author",
    )
    search_fields = (
        "title",
        "excerpt",
        "body",
        "author__name",
    )
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("author", "related_recipe")
    inlines = [ArticleImageInline]

    exclude = ("media_folder",)
    readonly_fields = ("hero_preview",)

    fieldsets = (
        (
            "Main information",
            {
                "fields": (
                    "title",
                    "slug",
                    "author",
                    "excerpt",
                    "related_recipe",
                )
            },
        ),
        (
            "Preview image",
            {
                "fields": (
                    "hero_image",
                    "hero_preview",
                )
            },
        ),
        (
            "Article content",
            {
                "fields": (
                    "body",
                )
            },
        ),
        (
            "Publishing",
            {
                "fields": (
                    "published",
                )
            },
        ),
    )

    def hero_preview(self, obj):
        if obj and obj.hero_image:
            return format_html(
                '<img src="{}" alt="Preview image" style="max-width: 320px; width: 100%; height: auto; border-radius: 14px; border: 1px solid #d8d2c8;" />',
                obj.hero_image.url,
            )
        return "No preview image uploaded yet."

    hero_preview.short_description = "Current preview"

    def article_preview_small(self, obj):
        if obj and obj.hero_image:
            return format_html(
                '<img src="{}" alt="Preview" style="width: 72px; height: 52px; object-fit: cover; border-radius: 8px; border: 1px solid #d8d2c8;" />',
                obj.hero_image.url,
            )
        return "—"

    article_preview_small.short_description = "Image"


@admin.register(ArticleImage)
class ArticleImageAdmin(admin.ModelAdmin):
    list_display = (
        "article",
        "image_preview_small",
        "sort_order",
        "is_active",
    )
    list_filter = (
        "is_active",
        "article",
        "article__author",
    )
    search_fields = (
        "article__title",
        "article__author__name",
        "alt_text",
        "caption",
    )
    ordering = (
        "article",
        "sort_order",
        "id",
    )
    readonly_fields = ("image_preview_large",)
    fields = (
        "article",
        "image",
        "image_preview_large",
        "alt_text",
        "caption",
        "sort_order",
        "is_active",
    )
    autocomplete_fields = ("article",)

    def image_preview_small(self, obj):
        if obj and obj.image:
            return format_html(
                '<img src="{}" alt="Gallery preview" style="width: 72px; height: 52px; object-fit: cover; border-radius: 8px; border: 1px solid #d8d2c8;" />',
                obj.image.url,
            )
        return "—"

    image_preview_small.short_description = "Image"

    def image_preview_large(self, obj):
        if obj and obj.image:
            return format_html(
                '<img src="{}" alt="Gallery preview" style="max-width: 320px; width: 100%; height: auto; border-radius: 14px; border: 1px solid #d8d2c8;" />',
                obj.image.url,
            )
        return "No image uploaded yet."

    image_preview_large.short_description = "Current preview"
