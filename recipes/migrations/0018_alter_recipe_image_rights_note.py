from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0017_recipe_legal_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recipe",
            name="image_rights_note",
            field=models.CharField(
                blank=True,
                help_text="Credit line or permission reference if any.",
                max_length=255,
                verbose_name="Image Credit / Licence",
            ),
        ),
    ]
