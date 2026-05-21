from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html_join

from config.profanity import find_profanity
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

    def clean(self):
        cleaned_data = super().clean()
        image_rights_status = cleaned_data.get("image_rights_status")
        image_rights_note = (cleaned_data.get("image_rights_note") or "").strip()
        source_type = cleaned_data.get("source_type")
        source_title = (cleaned_data.get("source_title") or "").strip()
        source_author = (cleaned_data.get("source_author") or "").strip()
        source_url = (cleaned_data.get("source_url") or "").strip()
        source_note = (cleaned_data.get("source_note") or "").strip()
        hero_image = cleaned_data.get("hero_image") or getattr(self.instance, "hero_image", None)
        active_gallery_exists = (
            self.instance.pk
            and self.instance.gallery_images.filter(is_active=True).exists()
        )

        if image_rights_status in {
            Article.ImageRightsStatus.LICENSED,
            Article.ImageRightsStatus.PUBLIC_DOMAIN,
        } and not image_rights_note:
            self.add_error(
                "image_rights_note",
                "Add the licence, credit line, or permission reference for this image status.",
            )

        if (
            image_rights_status == Article.ImageRightsStatus.NOT_APPLICABLE
            and (hero_image or active_gallery_exists)
        ):
            self.add_error(
                "image_rights_status",
                "Choose the correct image rights status when an article image is attached.",
            )

        if source_type == Article.SourceType.ADAPTED and not source_title:
            self.add_error(
                "source_title",
                "Add the source title for adapted articles.",
            )

        if (
            source_type == Article.SourceType.INSPIRED
            and not any([source_title, source_author, source_url, source_note])
        ):
            self.add_error(
                "source_note",
                "Add at least one source detail for inspired articles.",
            )

        _text_widgets = (forms.TextInput, forms.Textarea)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, _text_widgets):
                continue
            value = cleaned_data.get(field_name, "")
            if not value or not isinstance(value, str):
                continue
            bad = find_profanity(value)
            if bad:
                quoted = ", ".join(f'"{w}"' for w in bad)
                self.add_error(
                    field_name,
                    f"Contains forbidden words: {quoted}. Please remove them before publishing.",
                )

        return cleaned_data


class ArticleImageInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        article = self.instance

        if article.image_rights_status != Article.ImageRightsStatus.NOT_APPLICABLE:
            return

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            image = form.cleaned_data.get("image") or getattr(form.instance, "image", None)
            is_active = form.cleaned_data.get("is_active", True)
            if image and is_active:
                raise ValidationError(
                    "Choose the correct image rights status before attaching article gallery images."
                )


class ArticleImageInline(admin.TabularInline):
    model = ArticleImage
    formset = ArticleImageInlineFormSet
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
