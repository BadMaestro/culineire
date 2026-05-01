from django.db import migrations, models


def move_categories_to_culineire_set(apps, schema_editor):
    Recipe = apps.get_model("recipes", "Recipe")

    mapping = {
        "dinner_recipes": "dinner",
        "fruits_vegetables_and_other_produce": "vegetables",
        "bread_recipes": "bread_and_baking",
        "everyday_cooking": "everyday_irish_cooking",
        "lunch_recipes": "lunch",
        "ingredients": "ingredients",
        "us_recipes": "irish_cuisine",
        "appetizers_and_snacks": "light_bites_and_appetisers",
        "drinks": "drinks",
        "breakfast_and_brunch": "breakfast_and_brunch",
        "desserts": "desserts",
        "main_dishes": "main_courses",
        "side_dishes": "side_dishes",
        "trusted_brands": "irish_producers_and_brands",
        "healthy_recipes": "healthy_eating",
        "holidays_and_events": "seasonal_and_festive_irish",
        "cuisines": "irish_cuisine",
        "bbq_and_grilling": "grilling_and_barbecue",
        "meat_and_poultry": "meat_and_poultry",
        "seafood_recipes": "fish_and_seafood",
        "soups_stews_and_chili": "soups_and_stews",
        "pasta_and_noodles": "pasta_and_noodles",
        "salad_recipes": "salads",
        "irish_classic": "traditional_irish_dishes",
        "home_cooking": "everyday_irish_cooking",
        "restaurant_style": "main_courses",
        "vintage": "irish_culinary_heritage",
        "modern": "modern_irish_cooking",
    }

    for old_value, new_value in mapping.items():
        Recipe.objects.filter(category=old_value).update(category=new_value)

    Recipe.objects.filter(category="").update(category="everyday_irish_cooking")
    Recipe.objects.filter(category__isnull=True).update(category="everyday_irish_cooking")


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0004_alter_recipe_category"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recipe",
            name="category",
            field=models.CharField(
                choices=[
                    ("breakfast_and_brunch", "Breakfast and Brunch"),
                    ("lunch", "Lunch"),
                    ("dinner", "Dinner"),
                    ("light_bites_and_appetisers", "Light Bites and Appetisers"),
                    ("desserts", "Desserts"),
                    ("drinks", "Drinks"),
                    ("main_courses", "Main Courses"),
                    ("side_dishes", "Side Dishes"),
                    ("soups_and_stews", "Soups and Stews"),
                    ("salads", "Salads"),
                    ("pasta_and_noodles", "Pasta and Noodles"),
                    ("bread_and_baking", "Bread and Baking"),
                    ("grilling_and_barbecue", "Grilling and Barbecue"),
                    ("meat_and_poultry", "Meat and Poultry"),
                    ("fish_and_seafood", "Fish and Seafood"),
                    ("vegetables", "Vegetables"),
                    ("fruit", "Fruit"),
                    ("irish_cuisine", "Irish Cuisine"),
                    ("irish_culinary_heritage", "Irish Culinary Heritage"),
                    ("traditional_irish_dishes", "Traditional Irish Dishes"),
                    ("modern_irish_cooking", "Modern Irish Cooking"),
                    ("everyday_irish_cooking", "Everyday Irish Cooking"),
                    ("seasonal_and_festive_irish", "Seasonal and Festive (Irish)"),
                    ("healthy_eating", "Healthy Eating"),
                    ("ingredients", "Ingredients"),
                    ("irish_producers_and_brands", "Irish Producers and Brands"),
                ],
                default="everyday_irish_cooking",
                max_length=64,
            ),
        ),
        migrations.RunPython(move_categories_to_culineire_set, migrations.RunPython.noop),
    ]
