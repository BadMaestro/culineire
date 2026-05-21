from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0026_alter_recipe_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recipe",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("pending", "Pending Review"),
                    ("approved", "Approved"),
                    ("NEEDS_CHANGES", "Needs changes"),
                    ("rejected", "Rejected"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
    ]
