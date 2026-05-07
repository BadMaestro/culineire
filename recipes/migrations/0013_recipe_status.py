from django.db import migrations, models


def approve_existing_recipes(apps, schema_editor):
    Recipe = apps.get_model("recipes", "Recipe")
    Recipe.objects.all().update(status="approved")


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0012_recipeadditionalcategory"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipe",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending Review"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.RunPython(approve_existing_recipes, migrations.RunPython.noop),
    ]
