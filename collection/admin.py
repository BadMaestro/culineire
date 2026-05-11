from django.contrib import admin

from .models import SavedArticle, SavedRecipe


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
