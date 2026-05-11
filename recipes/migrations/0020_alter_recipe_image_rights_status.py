from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0019_alter_recipe_image_rights_status_default"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recipe",
            name="image_rights_status",
            field=models.CharField(
                "Image rights",
                choices=[
                    ("own", "My own photo"),
                    ("licensed", "Licensed (CC, stock, written permission)"),
                    ("public_domain", "Public domain"),
                    ("not_applicable", "No image uploaded"),
                ],
                default="own",
                max_length=20,
            ),
        ),
    ]
