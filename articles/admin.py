from django import forms
from django.contrib import admin
from django.utils.html import format_html_join

from .models import Article, ArticleImage


def _preview_image(url, alt_text, style):
    return format_html_join(
        "",
        '<img src="{}" alt="{}" style="{}" />',
        ((url, alt_text, style),),
    )


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

    @staticmethod
    @admin.display(description="Preview")
    def image_preview(obj):
        if obj and obj.image:
            return _preview_image(
                obj.image.url,
                "Gallery preview",
                "width: 120px; height: 90px; object-fit: cover; border-radius: 10px; border: 1px solid #d8d2c8;",
            )
        return "No image"


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleAdminForm
    list_display = (
        "title",
        "article_preview_small",
        "author",
        "status",
        "published",
        "related_recipe",
    )
    list_filter = (
        "status",
        "published",
        "author",
    )
    list_editable = ("status",)
    search_fields = (
        "title",
        "excerpt",
        "body",
        "author__name",
    )
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("author", "related_recipe")
    inlines = [ArticleImageInline]

    exclude = ("media_folder", "confirmed_by")
    readonly_fields = ("hero_preview", "confirmation_timestamp")

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
            "Image Rights",
            {
                "fields": (
                    "image_rights_status",
                    "image_rights_note",
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
            "Source Notes",
            {
                "fields": (
                    "source_type",
                    "source_title",
                    "source_author",
                    "source_url",
                    "source_note",
                )
            },
        ),
        (
            "Publishing",
            {
                "fields": (
                    "status",
                    "published",
                )
            },
        ),
        (
            "Author Confirmations",
            {
                "classes": ("collapse",),
                "fields": (
                    "confirmed_own_work",
                    "confirmed_image_rights",
                    "confirmed_rules",
                    "confirmation_timestamp",
                ),
            },
        ),
    )

    @staticmethod
    @admin.display(description="Current preview")
    def hero_preview(obj):
        if obj and obj.hero_image:
            return _preview_image(
                obj.hero_image.url,
                "Preview image",
                "max-width: 320px; width: 100%; height: auto; border-radius: 14px; border: 1px solid #d8d2c8;",
            )
        return "No preview image uploaded yet."

    @staticmethod
    @admin.display(description="Image")
    def article_preview_small(obj):
        if obj and obj.hero_image:
            return _preview_image(
                obj.hero_image.url,
                "Preview",
                "width: 72px; height: 52px; object-fit: cover; border-radius: 8px; border: 1px solid #d8d2c8;",
            )
        return "—"



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

    @staticmethod
    @admin.display(description="Image")
    def image_preview_small(obj):
        if obj and obj.image:
            return _preview_image(
                obj.image.url,
                "Gallery preview",
                "width: 72px; height: 52px; object-fit: cover; border-radius: 8px; border: 1px solid #d8d2c8;",
            )
        return "—"

    @staticmethod
    @admin.display(description="Current preview")
    def image_preview_large(obj):
        if obj and obj.image:
            return _preview_image(
                obj.image.url,
                "Gallery preview",
                "max-width: 320px; width: 100%; height: auto; border-radius: 14px; border: 1px solid #d8d2c8;",
            )
        return "No image uploaded yet."
