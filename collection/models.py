from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import UniqueConstraint


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


class SavedContent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_content_items",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="collection_saved_content_unique",
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["user", "-saved_at"]),
        ]
        ordering = ["-saved_at"]
        verbose_name = "Saved content"
        verbose_name_plural = "Saved content"

    def __str__(self):
        return f"{self.user} / {self.content_object}"


class ContentReaction(models.Model):
    class Reaction(models.TextChoices):
        LIKE = "like", "Like"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="content_reactions",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    reaction = models.CharField(max_length=20, choices=Reaction.choices, default=Reaction.LIKE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id", "reaction"],
                name="collection_content_reaction_unique",
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id", "reaction"]),
            models.Index(fields=["user", "-created_at"]),
        ]
        ordering = ["-created_at"]
        verbose_name = "Content reaction"
        verbose_name_plural = "Content reactions"

    def __str__(self):
        return f"{self.user} / {self.reaction} / {self.content_object}"


class AuthorFollow(models.Model):
    """A user subscribing to a RecipeAuthor's content."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following_authors",
    )
    author = models.ForeignKey(
        "recipes.RecipeAuthor",
        on_delete=models.CASCADE,
        related_name="followers",
    )
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["user", "author"], name="collection_author_follow_unique")
        ]
        indexes = [
            models.Index(fields=["user", "-followed_at"]),
            models.Index(fields=["author", "-followed_at"]),
        ]
        ordering = ["-followed_at"]
        verbose_name = "Author follow"
        verbose_name_plural = "Author follows"

    def __str__(self):
        return f"{self.user} follows {self.author}"
