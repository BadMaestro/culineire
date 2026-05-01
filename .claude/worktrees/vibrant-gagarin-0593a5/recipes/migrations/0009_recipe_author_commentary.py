from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0008_recipeauthor_avatar"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipe",
            name="author_commentary",
            field=models.TextField(blank=True),
        ),
    ]
