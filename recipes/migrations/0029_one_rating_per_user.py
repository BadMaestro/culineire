"""
Add UniqueConstraint to prevent duplicate ratings per authenticated user.
Also cleans up existing duplicate ratings (keeps the most recent one).
"""

from django.conf import settings
from django.db import migrations, models


def deduplicate_ratings(apps, schema_editor):
    """Remove duplicate ratings per (recipe, user), keeping only the latest."""
    RecipeRating = apps.get_model("recipes", "RecipeRating")
    from django.db.models import Max

    # Find authenticated users with duplicate ratings
    duplicates = (
        RecipeRating.objects
        .filter(user__isnull=False)
        .values("recipe", "user")
        .annotate(max_id=Max("id"))
        .filter(max_id__isnull=False)
    )

    # For each (recipe, user) pair, delete all but the latest
    for entry in duplicates:
        RecipeRating.objects.filter(
            recipe_id=entry["recipe"],
            user_id=entry["user"],
        ).exclude(id=entry["max_id"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0028_soft_delete"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(deduplicate_ratings, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="reciperating",
            constraint=models.UniqueConstraint(
                condition=models.Q(("user__isnull", False)),
                fields=["recipe", "user"],
                name="one_rating_per_user_per_recipe",
            ),
        ),
    ]
