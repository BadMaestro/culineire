from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0007_recipe_calories_recipecomment_reciperating"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipeauthor",
            name="avatar",
            field=models.ImageField(
                upload_to="authors/",
                blank=True,
                null=True,
            ),
        ),
    ]
