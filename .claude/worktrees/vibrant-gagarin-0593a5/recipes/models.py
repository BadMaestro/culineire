from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.text import slugify

from .validators import validate_image_upload

MAX_MEDIA_SEGMENT_LENGTH = 60


def safe_media_segment(value: str | None, fallback: str) -> str:
    slug = slugify((value or "").strip())[:MAX_MEDIA_SEGMENT_LENGTH].strip("-")
    return slug or fallback


def safe_author_folder(author) -> str:
    if author:
        return safe_media_segment(
            getattr(author, "slug", None) or getattr(author, "name", None),
            "author",
        )
    return "author"


def unique_media_folder_for_recipe(recipe) -> str:
    """
    Human-readable folder name for media storage.
    Unique per author, stable after first save.

    Examples:
    - Irish Stew
    - Irish Stew 2
    - Irish Stew 3
    """
    if getattr(recipe, "media_folder", None):
        return recipe.media_folder

    base_name = safe_media_segment(getattr(recipe, "title", ""), "recipe")

    author = getattr(recipe, "author", None)

    existing = Recipe.objects.exclude(pk=recipe.pk)
    if author:
        existing = existing.filter(author=author)
    else:
        existing = existing.filter(author__isnull=True)

    existing_names = set(
        existing.exclude(media_folder="")
        .values_list("media_folder", flat=True)
    )

    if base_name not in existing_names:
        return base_name

    counter = 2
    while True:
        candidate = f"{base_name} {counter}"
        if candidate not in existing_names:
            return candidate
        counter += 1


def recipe_base_folder(recipe) -> str:
    author_folder = safe_author_folder(getattr(recipe, "author", None))
    recipe_folder = unique_media_folder_for_recipe(recipe)
    return f"recipes/{author_folder}/{recipe_folder}"


def recipe_cover_upload_to(instance, filename: str) -> str:
    extension = Path(filename).suffix.lower() or ".jpg"
    return f"{recipe_base_folder(instance)}/cover{extension}"


def recipe_gallery_upload_to(instance, filename: str) -> str:
    extension = Path(filename).suffix.lower() or ".jpg"
    sort_order = instance.sort_order or 1
    return f"{recipe_base_folder(instance.recipe)}/gallery/img{sort_order}{extension}"


def author_avatar_upload_to(instance, filename: str) -> str:
    extension = Path(filename).suffix.lower() or ".jpg"
    author_folder = safe_author_folder(instance)
    return f"authors/{author_folder}/avatar{extension}"


class RecipeAuthor(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="recipe_author_profile",
        verbose_name="Linked user account",
    )
    name = models.CharField("Name / pen name", max_length=100)
    slug = models.SlugField("URL slug", unique=True)
    bio = models.TextField("Short author bio", blank=True)
    avatar = models.ImageField(
        upload_to=author_avatar_upload_to,
        blank=True,
        null=True,
        validators=[validate_image_upload],
    )

    class Meta:
        verbose_name = "Recipe author"
        verbose_name_plural = "Recipe authors"

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
        BREAKFAST_AND_BRUNCH = "breakfast_and_brunch", "Breakfast and Brunch"
        LUNCH = "lunch", "Lunch"
        DINNER = "dinner", "Dinner"
        LIGHT_BITES_AND_APPETISERS = "light_bites_and_appetisers", "Light Bites and Appetisers"
        DESSERTS = "desserts", "Desserts"
        DRINKS = "drinks", "Drinks"
        MAIN_COURSES = "main_courses", "Main Courses"
        SIDE_DISHES = "side_dishes", "Side Dishes"
        SOUPS_AND_STEWS = "soups_and_stews", "Soups and Stews"
        SALADS = "salads", "Salads"
        PASTA_AND_NOODLES = "pasta_and_noodles", "Pasta and Noodles"
        BREAD_AND_BAKING = "bread_and_baking", "Bread and Baking"
        GRILLING_AND_BARBECUE = "grilling_and_barbecue", "Grilling and Barbecue"
        MEAT_AND_POULTRY = "meat_and_poultry", "Meat and Poultry"
        FISH_AND_SEAFOOD = "fish_and_seafood", "Fish and Seafood"
        VEGETABLES = "vegetables", "Vegetables"
        FRUIT = "fruit", "Fruit"
        IRISH_CUISINE = "irish_cuisine", "Irish Cuisine"
        IRISH_CULINARY_HERITAGE = "irish_culinary_heritage", "Irish Culinary Heritage"
        TRADITIONAL_IRISH_DISHES = "traditional_irish_dishes", "Traditional Irish Dishes"
        MODERN_IRISH_COOKING = "modern_irish_cooking", "Modern Irish Cooking"
        EVERYDAY_IRISH_COOKING = "everyday_irish_cooking", "Everyday Irish Cooking"
        SEASONAL_AND_FESTIVE_IRISH = "seasonal_and_festive_irish", "Seasonal and Festive (Irish)"
        HEALTHY_EATING = "healthy_eating", "Healthy Eating"
        INGREDIENTS = "ingredients", "Ingredients"
        IRISH_PRODUCERS_AND_BRANDS = "irish_producers_and_brands", "Irish Producers and Brands"

    class SourceType(models.TextChoices):
        ORIGINAL = "original", "Original"
        FAMILY = "family", "Family recipe"
        COOKBOOK = "cookbook", "Cookbook"
        WEBSITE = "website", "Website"
        RESTAURANT = "restaurant", "Restaurant"
        OTHER = "other", "Other"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, db_index=True, blank=True)
    media_folder = models.CharField(max_length=255, blank=True, editable=False, db_index=True)

    author = models.ForeignKey(
        RecipeAuthor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recipes",
        verbose_name="Author",
    )

    short_description = models.TextField(blank=True)

    hero_image = models.ImageField(
        upload_to=recipe_cover_upload_to,
        blank=True,
        null=True,
        validators=[validate_image_upload],
        verbose_name="Preview image",
    )

    prep_time_minutes = models.PositiveSmallIntegerField(default=0)
    cook_time_minutes = models.PositiveSmallIntegerField(default=0)
    servings = models.PositiveSmallIntegerField(default=1)

    calories = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional calories per serving.",
    )

    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.EASY,
    )

    category = models.CharField(
        max_length=64,
        choices=Category.choices,
        default=Category.EVERYDAY_IRISH_COOKING,
    )

    ingredients = models.TextField(help_text="One ingredient per line.")
    method = models.TextField(help_text="Step-by-step method.")
    tips = models.TextField(blank=True)
    irish_context = models.TextField(blank=True)
    author_commentary = models.TextField(blank=True)
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

    def get_absolute_url(self):
        return reverse("recipes:recipe_detail", kwargs={"slug": self.slug})

    @property
    def total_time_minutes(self) -> int:
        return (self.prep_time_minutes or 0) + (self.cook_time_minutes or 0)

    @property
    def average_rating(self):
        return self.ratings.aggregate(avg=models.Avg("value"))["avg"] or 0

    @property
    def ratings_count(self):
        return self.ratings.count()

    @property
    def approved_comments(self):
        return self.comments.filter(is_approved=True)

    @classmethod
    def get_category_value_from_slug(cls, category_slug: str) -> str | None:
        value = category_slug.replace("-", "_")
        valid_values = {choice.value for choice in cls.Category}
        return value if value in valid_values else None

    @classmethod
    def get_category_label(cls, category_value: str) -> str:
        return cls.Category(category_value).label

    @classmethod
    def get_category_navigation(cls, selected_value: str | None = None) -> list[dict]:
        items = []

        for choice in cls.Category:
            category_slug = choice.value.replace("_", "-")
            items.append(
                {
                    "value": choice.value,
                    "label": choice.label,
                    "slug": category_slug,
                    "url": reverse("recipes:category_detail", kwargs={"category_slug": category_slug}),
                    "is_active": choice.value == selected_value,
                }
            )

        return items

    @classmethod
    def get_category_url_for_value(cls, category_value: str) -> str:
        return reverse(
            "recipes:category_detail",
            kwargs={"category_slug": category_value.replace("_", "-")},
        )

    @classmethod
    def filter_for_category(cls, queryset, category_value: str):
        return queryset.filter(
            Q(category=category_value) | Q(additional_category_links__category=category_value)
        ).distinct()

    def get_category_url(self) -> str:
        if not self.category:
            return reverse("recipes:recipe_list")

        return self.get_category_url_for_value(self.category)

    def get_additional_category_values(self) -> list[str]:
        if not self.pk:
            return []

        return list(
            self.additional_category_links.order_by("id").values_list("category", flat=True)
        )

    def get_all_category_values(self) -> list[str]:
        values = []
        if self.category:
            values.append(self.category)

        for value in self.get_additional_category_values():
            if value and value not in values:
                values.append(value)

        return values

    def get_all_category_items(self) -> list[dict]:
        return [
            {
                "value": value,
                "label": self.get_category_label(value),
                "url": self.get_category_url_for_value(value),
                "is_primary": value == self.category,
            }
            for value in self.get_all_category_values()
        ]

    def generate_unique_slug(self) -> str:
        base_slug = slugify(self.title)[:200] or "recipe"
        slug = base_slug
        counter = 2

        while Recipe.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            suffix = f"-{counter}"
            slug = f"{base_slug[:220 - len(suffix)]}{suffix}"
            counter += 1

        return slug

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = self.generate_unique_slug()

        if not self.media_folder:
            self.media_folder = unique_media_folder_for_recipe(self)

        super().save(*args, **kwargs)


class RecipeAdditionalCategory(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="additional_category_links",
    )
    category = models.CharField(
        max_length=64,
        choices=Recipe.Category.choices,
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "category"],
                name="recipes_additional_category_unique_per_recipe",
            ),
        ]
        verbose_name = "Additional recipe category"
        verbose_name_plural = "Additional recipe categories"

    def __str__(self) -> str:
        return f"{self.recipe.title} â€” {self.get_category_display()}"


class RecipeImage(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )
    image = models.ImageField(
        upload_to=recipe_gallery_upload_to,
        validators=[validate_image_upload],
    )
    alt_text = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Recipe gallery image"
        verbose_name_plural = "Recipe gallery images"

    def __str__(self) -> str:
        return f"{self.recipe.title} — image {self.id}"


class RecipeRating(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    value = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(value__gte=1) & models.Q(value__lte=5),
                name="recipe_rating_value_between_1_and_5",
            ),
        ]
        verbose_name = "Recipe rating"
        verbose_name_plural = "Recipe ratings"

    def __str__(self) -> str:
        return f"{self.recipe.title} — {self.value}/5"


class RecipeComment(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    name = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Recipe comment"
        verbose_name_plural = "Recipe comments"

    def __str__(self) -> str:
        return f"Comment by {self.name} on {self.recipe.title}"
