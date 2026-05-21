from django import forms
from django.contrib import admin
from django.utils.html import format_html_join

from config.profanity import find_profanity
from .allergens import EU_ALLERGEN_CHOICES, parse_selected_allergen_keys, serialize_allergen_keys
from .models import (
    Recipe,
    RecipeAuthor,
    RecipeComment,
    RecipeImage,
    RecipeRating,
)


def _preview_image(url, alt_text, style):
    return format_html_join(
        "",
        '<img src="{}" alt="{}" style="{}" />',
        ((url, alt_text, style),),
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

    def clean(self):
        cleaned_data = super().clean()
        image_rights_status = cleaned_data.get("image_rights_status")
        image_rights_note = (cleaned_data.get("image_rights_note") or "").strip()
        source_type = cleaned_data.get("source_type")
        source_title = (cleaned_data.get("source_title") or "").strip()
        source_author = (cleaned_data.get("source_author") or "").strip()
        source_url = (cleaned_data.get("source_url") or "").strip()
        source_note = (cleaned_data.get("source_note") or "").strip()

        if (
            image_rights_status in {
                Recipe.ImageRightsStatus.LICENSED,
                Recipe.ImageRightsStatus.PUBLIC_DOMAIN,
            }
            and not image_rights_note
        ):
            self.add_error(
                "image_rights_note",
                "Add the licence, credit line, or permission reference for this image status.",
            )

        if source_type != Recipe.SourceType.ORIGINAL and not any(
            [source_title, source_author, source_url, source_note]
        ):
            self.add_error(
                "source_note",
                "Add at least one source detail for recipes based on an external source.",
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

    @staticmethod
    @admin.display(description="Preview")
    def image_preview(obj):
        if obj and obj.image:
            return _preview_image(
                obj.image.url,
                "Gallery image preview",
                "max-width: 120px; max-height: 120px; border-radius: 8px;",
            )
        return "No image"


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

    @staticmethod
    @admin.display(description="Current avatar")
    def avatar_preview(obj):
        if obj and obj.avatar:
            return _preview_image(
                obj.avatar.url,
                "Author avatar preview",
                "max-width: 160px; max-height: 160px; border-radius: 999px;",
            )
        return "No avatar uploaded yet."


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    form = RecipeAdminForm
    change_form_template = "admin/recipes/recipe/change_form.html"
    list_display = ("title", "status", "is_deleted", "category", "difficulty", "author", "created_at")
    list_filter = ("status", "is_deleted", "category", "difficulty", "author", "source_type", "created_at")
    search_fields = ("title", "short_description", "ingredients", "method")
    date_hierarchy = "created_at"
    autocomplete_fields = ("author",)
    ordering = ("-created_at",)
    inlines = [RecipeImageInline]
    exclude = ("slug", "media_folder", "confirmed_by")
    readonly_fields = ("hero_preview", "confirmation_timestamp", "moderated_by", "moderated_at", "deleted_at", "deleted_by")

    fieldsets = (
        (
            "Main",
            {
                "fields": (
                    "title",
                    "author",
                    "status",
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
        (
            "Image rights",
            {
                "fields": (
                    "image_rights_status",
                    "image_rights_note",
                )
            },
        ),
        (
            "Moderation",
            {
                "classes": ("collapse",),
                "fields": (
                    "moderation_note",
                    "moderated_by",
                    "moderated_at",
                ),
            },
        ),
        (
            "Soft delete",
            {
                "classes": ("collapse",),
                "fields": (
                    "is_deleted",
                    "deleted_at",
                    "deleted_by",
                ),
            },
        ),
        (
            "Author confirmations",
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
                "max-width: 240px; border-radius: 10px;",
            )
        return "No preview image uploaded yet."

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
