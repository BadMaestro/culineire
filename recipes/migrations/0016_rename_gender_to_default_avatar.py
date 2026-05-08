from django.db import migrations, models


def prefer_not_to_say_to_neutral(apps, schema_editor):
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")
    RecipeAuthor.objects.filter(default_avatar="prefer_not_to_say").update(default_avatar="neutral")


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0015_recipeauthor_gender"),
    ]

    operations = [
        migrations.RenameField(
            model_name="recipeauthor",
            old_name="gender",
            new_name="default_avatar",
        ),
        migrations.RunPython(prefer_not_to_say_to_neutral, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="recipeauthor",
            name="default_avatar",
            field=models.CharField(
                choices=[
                    ("male", "Male Avatar"),
                    ("female", "Female Avatar"),
                    ("neutral", "Neutral Avatar"),
                ],
                default="neutral",
                max_length=24,
                verbose_name="Default avatar",
            ),
        ),
    ]
