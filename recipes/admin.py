from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Recipe,
    RecipeAuthor,
    RecipeComment,
    RecipeImage,
    RecipeRating,
)


class RecipeAdminForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = "__all__"
        labels = {
            "hero_image": "Preview image",
        }
        help_texts = {
            "hero_image": "This is the main recipe image shown on cards and on the recipe page.",
            "calories": "Optional calories per serving.",
        }


class RecipeImageInline(admin.TabularInline):
    model = RecipeImage
    extra = 1
    fields = ("image_preview", "image", "alt_text", "caption", "sort_order", "is_active")
    readonly_fields = ("image_preview",)
    ordering = ("sort_order", "id")

    def image_preview(self, obj):
        if obj and obj.image:
            return format_html(
                '<img src="{}" style="max-width: 120px; max-height: 120px; border-radius: 8px;" alt="Gallery image preview" />',
                obj.image.url,
            )
        return "No image"

    image_preview.short_description = "Preview"


@admin.register(RecipeAuthor)
class RecipeAuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "bio")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    form = RecipeAdminForm
    change_form_template = "admin/recipes/recipe/change_form.html"
    list_display = ("title", "category", "difficulty", "author", "created_at")
    list_filter = ("category", "difficulty", "author", "source_type", "created_at")
    search_fields = ("title", "short_description", "ingredients", "method")
    date_hierarchy = "created_at"
    autocomplete_fields = ("author",)
    ordering = ("-created_at",)
    inlines = [RecipeImageInline]
    exclude = ("slug", "media_folder")
    readonly_fields = ("hero_preview",)

    fieldsets = (
        (
            "Main",
            {
                "fields": (
                    "title",
                    "author",
                    "short_description",
                    "hero_image",
                    "hero_preview",
                )
            },
        ),
        (
            "Recipe details",
            {
                "fields": (
                    "prep_time_minutes",
                    "cook_time_minutes",
                    "servings",
                    "calories",
                    "difficulty",
                    "category",
                )
            },
        ),
        (
            "Content",
            {
                "fields": (
                    "ingredients",
                    "method",
                    "tips",
                    "irish_context",
                    "allergens",
                )
            },
        ),
        (
            "Source",
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
    )

    def hero_preview(self, obj):
        if obj and obj.hero_image:
            return format_html(
                '<img src="{}" style="max-width: 240px; border-radius: 10px;" alt="Preview image" />',
                obj.hero_image.url,
            )
        return "No preview image uploaded yet."

    hero_preview.short_description = "Current preview"


@admin.register(RecipeImage)
class RecipeImageAdmin(admin.ModelAdmin):
    list_display = ("recipe", "sort_order", "is_active")
    list_filter = ("is_active", "recipe")
    search_fields = ("recipe__title", "alt_text", "caption")
    ordering = ("recipe", "sort_order", "id")


@admin.register(RecipeRating)
class RecipeRatingAdmin(admin.ModelAdmin):
    list_display = ("recipe", "value", "created_at")
    list_filter = ("value", "created_at")
    search_fields = ("recipe__title",)
    ordering = ("-created_at",)


@admin.register(RecipeComment)
class RecipeCommentAdmin(admin.ModelAdmin):
    list_display = ("recipe", "name", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("recipe__title", "name", "content")
    ordering = ("-created_at",)
    list_editable = ("is_approved",)
