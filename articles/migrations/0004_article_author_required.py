import django.db.models.deletion
from django.db import migrations, models


def assign_default_author(apps, schema_editor):
    Article = apps.get_model("articles", "Article")
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")

    default_author = RecipeAuthor.objects.filter(slug="greenbear").first()
    if default_author is None:
        default_author = RecipeAuthor.objects.order_by("id").first()

    if default_author is None:
        default_author = RecipeAuthor.objects.create(
            name="GreenBear",
            slug="greenbear",
            bio="Recipe author and founder of this kitchen.",
        )

    Article.objects.filter(author__isnull=True).update(author=default_author)


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0001_initial"),
        ("articles", "0003_article_media_folder_article_hero_image_articleimage_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="author",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="articles",
                to="recipes.recipeauthor",
                verbose_name="Author",
            ),
        ),
        migrations.RunPython(assign_default_author, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="article",
            name="author",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="articles",
                to="recipes.recipeauthor",
                verbose_name="Author",
            ),
        ),
    ]
