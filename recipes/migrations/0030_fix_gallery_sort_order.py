"""
Fix gallery images where all images share sort_order=1.
Re-numbers them sequentially (1, 2, 3, ...) based on creation order.
"""

from django.db import migrations


def fix_sort_orders(apps, schema_editor):
    """Re-number gallery images that share the same sort_order within a recipe."""
    RecipeImage = apps.get_model("recipes", "RecipeImage")
    recipe_ids = (
        RecipeImage.objects
        .filter(is_active=True)
        .values_list("recipe_id", flat=True)
        .distinct()
    )
    for recipe_id in recipe_ids:
        images = list(
            RecipeImage.objects
            .filter(recipe_id=recipe_id, is_active=True)
            .order_by("sort_order", "id")
        )
        needs_update = False
        seen = set()
        for img in images:
            if img.sort_order in seen:
                needs_update = True
                break
            seen.add(img.sort_order)

        if needs_update:
            for idx, img in enumerate(images, start=1):
                if img.sort_order != idx:
                    img.sort_order = idx
                    img.save(update_fields=["sort_order"])


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0029_one_rating_per_user"),
    ]

    operations = [
        migrations.RunPython(fix_sort_orders, migrations.RunPython.noop),
    ]
