from django.db import migrations


def create_full_irish(apps, schema_editor):
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")
    Recipe = apps.get_model("recipes", "Recipe")

    author = (
        RecipeAuthor.objects.filter(name__icontains="jam").first()
        or RecipeAuthor.objects.filter(slug__icontains="jam").first()
    )
    if author is None:
        return

    if Recipe.objects.filter(slug="full-irish-breakfast").exists():
        return

    Recipe.objects.create(
        title="Full Irish Breakfast",
        slug="full-irish-breakfast",
        short_description=(
            "A proper full Irish: back rashers, pork sausages, free-range egg, "
            "white and black pudding, grilled tomato, sauteed mushrooms, baked beans "
            "and brown soda bread toast. Everything cooked right, nothing rushed."
        ),
        hero_image_alt_text=(
            "Full Irish breakfast on a white plate with rashers, sausages, "
            "egg, pudding, tomato, mushrooms and toast"
        ),
        image_rights_status="not_applicable",
        category="breakfast_and_brunch",
        difficulty="easy",
        prep_time_minutes=15,
        cook_time_minutes=25,
        servings=1,
        ingredients=(
            "Back rashers (bacon)\n"
            "Pork sausages\n"
            "Free-range eggs\n"
            "White pudding\n"
            "Black pudding\n"
            "Grilled tomato\n"
            "Sauteed mushrooms\n"
            "Baked beans\n"
            "Brown soda bread toast\n"
            "Butter"
        ),
        method=(
            "1. Heat a large frying pan over medium-high heat with a little oil.\n"
            "2. Fry the back rashers 3-4 minutes per side until golden and crisp. Set aside, keep warm.\n"
            "3. Cook pork sausages in the same pan 12-15 minutes, turning regularly, until deep golden all over.\n"
            "4. Slice white and black pudding into 1cm rounds. Fry 2-3 minutes per side until caramelised.\n"
            "5. Halve the tomato, season, grill cut-side up for 6-8 minutes until softened and lightly charred.\n"
            "6. Saute mushrooms in butter over high heat 3-4 minutes until golden.\n"
            "7. Heat baked beans gently in a small saucepan.\n"
            "8. Fry the eggs in fresh butter on low heat until whites are just set and yolk stays runny.\n"
            "9. Toast the brown soda bread and butter while hot.\n"
            "10. Arrange on a warmed plate and serve immediately with strong tea."
        ),
        tips=(
            "Use a cast-iron pan for the rashers and sausages. "
            "Keep everything warm in a low oven (100C) while you finish the eggs."
        ),
        irish_context=(
            "The full Irish breakfast has been a cornerstone of Irish hospitality since the 19th century, "
            "evolving from a farmhouse meal into the definitive weekend tradition across the island."
        ),
        confirmed_own_work=True,
        confirmed_image_rights=True,
        confirmed_rules=True,
        author=author,
        status="approved",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0035_recipeauthor_can_generate_ai_images"),
    ]

    operations = [
        migrations.RunPython(create_full_irish, migrations.RunPython.noop),
    ]
