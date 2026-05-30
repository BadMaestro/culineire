from django.contrib import admin

from .models import ContentReaction, SavedArticle, SavedContent, SavedRecipe


@admin.register(SavedRecipe)
class SavedRecipeAdmin(admin.ModelAdmin):
    list_display = ("user", "recipe", "saved_at")
    list_select_related = ("user", "recipe")
    raw_id_fields = ("user", "recipe")


@admin.register(SavedArticle)
class SavedArticleAdmin(admin.ModelAdmin):
    list_display = ("user", "article", "saved_at")
    list_select_related = ("user", "article")
    raw_id_fields = ("user", "article")


@admin.register(SavedContent)
class SavedContentAdmin(admin.ModelAdmin):
    list_display = ("user", "content_type", "object_id", "saved_at")
    list_filter = ("content_type", "saved_at")
    raw_id_fields = ("user", "content_type")


@admin.register(ContentReaction)
class ContentReactionAdmin(admin.ModelAdmin):
    list_display = ("user", "content_type", "object_id", "reaction", "created_at")
    list_filter = ("content_type", "reaction", "created_at")
    raw_id_fields = ("user", "content_type")
