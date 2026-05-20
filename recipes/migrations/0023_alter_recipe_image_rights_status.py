from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0022_recipecomment_author_recipecomment_parent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recipe",
            name="image_rights_status",
            field=models.CharField(
                "Image rights",
                choices=[
                    ("own", "My own photo"),
                    ("ai_generated", "AI generated image"),
                    ("licensed", "Licensed (CC, stock, written permission)"),
                    ("public_domain", "Public domain"),
                    ("not_applicable", "No image uploaded"),
                ],
                default="own",
                max_length=20,
            ),
        ),
    ]
