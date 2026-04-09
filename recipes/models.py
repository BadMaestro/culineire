from __future__ import annotations

from django.db import models
from django.utils.text import slugify
from django.urls import reverse


class RecipeAuthor(models.Model):
    name = models.CharField("Имя / псевдоним", max_length=100)
    slug = models.SlugField("Slug для URL", unique=True)
    bio = models.TextField("Кратко об авторе", blank=True)

    class Meta:
        verbose_name = "Автор рецепта"
        verbose_name_plural = "Авторы рецептов"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("recipes:author_detail", kwargs={"slug": self.slug})


class Recipe(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    class Category(models.TextChoices):
        IRISH_CLASSIC = "irish_classic", "Irish classic"
        HOME_COOKING = "home_cooking", "Home cooking"
        RESTAURANT_STYLE = "restaurant_style", "Restaurant-style at home"
        VINTAGE = "vintage", "Vintage / Old cookbooks"
        MODERN = "modern", "Modern & experimental"

    class SourceType(models.TextChoices):
        ORIGINAL = "original", "Original"
        FAMILY = "family", "Family recipe"
        COOKBOOK = "cookbook", "Cookbook"
        WEBSITE = "website", "Website"
        RESTAURANT = "restaurant", "Restaurant"
        OTHER = "other", "Other"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, db_index=True)

    author = models.ForeignKey(
        RecipeAuthor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recipes",
        verbose_name="Автор",
    )

    short_description = models.TextField(blank=True)

    hero_image = models.ImageField(
        upload_to="recipes/",
        blank=True,
        null=True,
    )

    prep_time_minutes = models.PositiveSmallIntegerField(default=0)
    cook_time_minutes = models.PositiveSmallIntegerField(default=0)
    servings = models.PositiveSmallIntegerField(default=1)

    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.EASY,
    )

    category = models.CharField(
        max_length=32,
        choices=Category.choices,
        default=Category.HOME_COOKING,
    )

    ingredients = models.TextField(help_text="One ingredient per line.")
    method = models.TextField(help_text="Step-by-step method.")
    tips = models.TextField(blank=True)
    irish_context = models.TextField(blank=True)
    allergens = models.TextField(blank=True)

    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.ORIGINAL,
    )
    source_title = models.CharField(max_length=255, blank=True)
    source_author = models.CharField(max_length=255, blank=True)
    source_url = models.URLField(blank=True)
    source_note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def total_time_minutes(self) -> int:
        return (self.prep_time_minutes or 0) + (self.cook_time_minutes or 0)

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        super().save(*args, **kwargs)
