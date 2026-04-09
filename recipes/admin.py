from django.contrib import admin

from .models import Recipe, RecipeAuthor


@admin.register(RecipeAuthor)
class RecipeAuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "bio")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "difficulty", "author", "created_at")
    list_filter = ("category", "difficulty", "author", "source_type", "created_at")
    search_fields = ("title", "short_description", "ingredients", "method")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "created_at"
    autocomplete_fields = ("author",)
    ordering = ("-created_at",)
