from django.conf import settings
from django.db import models


class SavedRecipe(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_recipes",
    )
    recipe = models.ForeignKey(
        "recipes.Recipe",
        on_delete=models.CASCADE,
        related_name="saved_by",
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "recipe"], name="collection_saved_recipe_unique")
        ]
        ordering = ["-saved_at"]
        verbose_name = "Saved recipe"
        verbose_name_plural = "Saved recipes"

    def __str__(self):
        return f"{self.user} / {self.recipe}"


class SavedArticle(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_articles",
    )
    article = models.ForeignKey(
        "articles.Article",
        on_delete=models.CASCADE,
        related_name="saved_by",
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "article"], name="collection_saved_article_unique")
        ]
        ordering = ["-saved_at"]
        verbose_name = "Saved article"
        verbose_name_plural = "Saved articles"

    def __str__(self):
        return f"{self.user} / {self.article}"
