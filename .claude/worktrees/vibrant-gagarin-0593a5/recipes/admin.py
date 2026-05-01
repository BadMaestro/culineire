from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .allergens import EU_ALLERGEN_CHOICES, parse_selected_allergen_keys, serialize_allergen_keys
from .models import (
    Recipe,
    RecipeAuthor,
    RecipeComment,
    RecipeImage,
    RecipeRating,
)


class RecipeAdminForm(forms.ModelForm):
    selected_allergens = forms.MultipleChoiceField(
        label="Allergens",
        choices=EU_ALLERGEN_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "allergen-checklist"}),
        help_text="Tick any of the 14 allergens that are present in this recipe.",
    )
    additional_categories = forms.MultipleChoiceField(
        label="Additional categories",
        choices=Recipe.Category.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "authoring-checkbox-list"}),
        help_text="Optional extra categories this recipe should also appear in.",
    )

    class Meta:
        model = Recipe
        fields = "__all__"
        labels = {
            "hero_image": "Preview image",
            "author_commentary": "Author commentary",
        }
        help_texts = {
            "hero_image": "This is the main recipe image shown on cards and on the recipe page.",
            "calories": "Optional calories per serving.",
            "author_commentary": "Optional note from the author. This block stays hidden on the site when left empty.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["selected_allergens"].initial = parse_selected_allergen_keys(
            getattr(self.instance, "allergens", "")
        )
        self.fields["additional_categories"].initial = self.instance.get_additional_category_values()

    def clean_additional_categories(self):
        selected = []
        primary_category = self.cleaned_data.get("category")

        for value in self.cleaned_data.get("additional_categories", []):
            if value == primary_category or value in selected:
                continue
            selected.append(value)

        return selected

    def save_additional_categories(self, instance):
        selected = self.cleaned_data.get("additional_categories", [])
        instance.additional_category_links.exclude(category__in=selected).delete()

        existing = set(instance.additional_category_links.values_list("category", flat=True))
        for category_value in selected:
            if category_value not in existing:
                instance.additional_category_links.create(category=category_value)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.allergens = serialize_allergen_keys(self.cleaned_data["selected_allergens"])
        if commit:
            instance.save()
            self.save_m2m()
            self.save_additional_categories(instance)
        return instance


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
    list_display = ("name", "slug", "user")
    search_fields = ("name", "bio", "user__username", "user__email")
    autocomplete_fields = ("user",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("avatar_preview",)
    fieldsets = (
        (
            "Author details",
            {
                "fields": (
                    "user",
                    "name",
                    "slug",
                    "bio",
                    "avatar",
                    "avatar_preview",
                ),
            },
        ),
    )

    def avatar_preview(self, obj):
        if obj and obj.avatar:
            return format_html(
                '<img src="{}" style="max-width: 160px; max-height: 160px; border-radius: 999px;" alt="Author avatar preview" />',
                obj.avatar.url,
            )
        return "No avatar uploaded yet."

    avatar_preview.short_description = "Current avatar"


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
                    "additional_categories",
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
                    "author_commentary",
                    "selected_allergens",
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

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if hasattr(form, "save_additional_categories"):
            form.save_additional_categories(form.instance)


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
