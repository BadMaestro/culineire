from django.db import migrations, models


def move_old_category_values(apps, schema_editor):
    Recipe = apps.get_model("recipes", "Recipe")

    mapping = {
        "irish_classic": "cuisines",
        "home_cooking": "everyday_cooking",
        "restaurant_style": "main_dishes",
        "vintage": "everyday_cooking",
        "modern": "main_dishes",
    }

    for old_value, new_value in mapping.items():
        Recipe.objects.filter(category=old_value).update(category=new_value)


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0003_remove_recipe_media_uid_recipe_media_folder_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recipe",
            name="category",
            field=models.CharField(
                choices=[
                    ("dinner_recipes", "Dinner Recipes"),
                    ("fruits_vegetables_and_other_produce", "Fruits, Vegetables and Other Produce"),
                    ("bread_recipes", "Bread Recipes"),
                    ("everyday_cooking", "Everyday Cooking"),
                    ("lunch_recipes", "Lunch Recipes"),
                    ("ingredients", "Ingredients"),
                    ("us_recipes", "U.S. Recipes"),
                    ("appetizers_and_snacks", "Appetizers and Snacks"),
                    ("drinks", "Drinks"),
                    ("breakfast_and_brunch", "Breakfast and Brunch"),
                    ("desserts", "Desserts"),
                    ("main_dishes", "Main Dishes"),
                    ("side_dishes", "Side Dishes"),
                    ("trusted_brands", "Trusted Brands"),
                    ("healthy_recipes", "Healthy Recipes"),
                    ("holidays_and_events", "Holidays and Events"),
                    ("cuisines", "Cuisines"),
                    ("bbq_and_grilling", "BBQ & Grilling"),
                    ("meat_and_poultry", "Meat and Poultry"),
                    ("seafood_recipes", "Seafood Recipes"),
                    ("soups_stews_and_chili", "Soups, Stews and Chili"),
                    ("pasta_and_noodles", "Pasta and Noodles"),
                    ("salad_recipes", "Salad Recipes"),
                ],
                default="everyday_cooking",
                max_length=64,
            ),
        ),
        migrations.RunPython(move_old_category_values, migrations.RunPython.noop),
    ]
