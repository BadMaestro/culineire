from django.db import migrations


def create_full_irish(apps, schema_editor):
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")
    Recipe = apps.get_model("recipes", "Recipe")

    author = RecipeAuthor.objects.filter(slug="dmitrij-golovin").first()
    if author is None:
        return

    if Recipe.objects.filter(slug="full-irish-breakfast-crestedten").exists():
        return

    Recipe.objects.create(
        title="Full Irish Breakfast — CrestedTen Style",
        slug="full-irish-breakfast-crestedten",
        short_description=(
            "CrestedTen's take on the full Irish: thick-cut dry-cured rashers, "
            "hand-linked pork sausages, soft-fried free-range egg, sliced white and black pudding, "
            "roasted cherry tomatoes, wild mushrooms in garlic butter, and sourdough toast. "
            "No shortcuts. No compromises."
        ),
        hero_image_alt_text=(
            "Full Irish breakfast by CrestedTen on a slate plate with thick rashers, "
            "sausages, egg, pudding, roasted tomatoes, wild mushrooms and sourdough toast"
        ),
        image_rights_status="not_applicable",
        category="breakfast_and_brunch",
        difficulty="easy",
        prep_time_minutes=10,
        cook_time_minutes=25,
        servings=1,
        ingredients=(
            "Thick-cut dry-cured back rashers\n"
            "Hand-linked pork sausages\n"
            "Free-range egg\n"
            "White pudding\n"
            "Black pudding\n"
            "Cherry tomatoes on the vine\n"
            "Wild mushrooms in garlic butter\n"
            "Baked beans\n"
            "Sourdough toast\n"
            "Unsalted butter"
        ),
        method=(
            "1. Preheat oven to 180C. Place cherry tomatoes on a tray, drizzle with oil, season. "
            "Roast 15 minutes until blistered.\n"
            "2. Heat a cast-iron pan over medium heat. Add rashers and cook 3-4 minutes per side "
            "until caramelised at the edges. Rest on a warm plate.\n"
            "3. In the same pan, cook sausages on medium-low 15 minutes, turning every 3 minutes "
            "for even colour all round.\n"
            "4. Slice pudding 1.5cm thick. Fry in a dry pan 2 minutes per side until a dark crust forms.\n"
            "5. Melt butter in a separate pan over high heat. Add crushed garlic and wild mushrooms. "
            "Cook 4 minutes tossing until golden. Season.\n"
            "6. Reduce heat to low. Add a fresh knob of butter and fry the egg slowly until "
            "whites are set and yolk is runny and glossy.\n"
            "7. Toast sourdough until golden. Butter immediately.\n"
            "8. Build the plate: everything hot, everything rested, nothing touching unnecessarily. "
            "Serve at once."
        ),
        tips=(
            "Thick-cut dry-cured rashers are essential — they hold their shape and develop a proper "
            "crust. Supermarket thin rashers shrink and go rubbery. If you can, buy from a butcher."
        ),
        irish_context=(
            "The full Irish is Ireland's most democratic dish — eaten after mass, after a match, "
            "after a late night, and on every slow Sunday morning across the island. "
            "Getting it right is a matter of national pride."
        ),
        author_commentary=(
            "This is the version I cook when I want to win. Every element is treated as its own "
            "discipline. The egg is the hardest part — get the egg right and the plate speaks for itself."
        ),
        confirmed_own_work=True,
        confirmed_image_rights=True,
        confirmed_rules=True,
        author=author,
        status="approved",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0036_jam_oliver_full_irish"),
    ]

    operations = [
        migrations.RunPython(create_full_irish, migrations.RunPython.noop),
    ]
