from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0013_recipe_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipeauthor",
            name="has_bearseeker_privileges",
            field=models.BooleanField(
                default=False,
                help_text="Allows this author to use CulinEire moderation tools without Django admin access.",
                verbose_name="Can moderate site content",
            ),
        ),
    ]
