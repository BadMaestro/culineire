import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("articles", "0007_article_status"),
        ("recipes", "0016_rename_gender_to_default_avatar"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SavedRecipe",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("saved_at", models.DateTimeField(auto_now_add=True)),
                ("recipe", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_by", to="recipes.recipe")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_recipes", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Saved recipe",
                "verbose_name_plural": "Saved recipes",
                "ordering": ["-saved_at"],
            },
        ),
        migrations.CreateModel(
            name="SavedArticle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("saved_at", models.DateTimeField(auto_now_add=True)),
                ("article", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_by", to="articles.article")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_articles", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Saved article",
                "verbose_name_plural": "Saved articles",
                "ordering": ["-saved_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="savedrecipe",
            constraint=models.UniqueConstraint(fields=["user", "recipe"], name="collection_saved_recipe_unique"),
        ),
        migrations.AddConstraint(
            model_name="savedarticle",
            constraint=models.UniqueConstraint(fields=["user", "article"], name="collection_saved_article_unique"),
        ),
    ]
