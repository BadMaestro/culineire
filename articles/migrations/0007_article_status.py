from django.db import migrations, models


def approve_existing_articles(apps, schema_editor):
    Article = apps.get_model("articles", "Article")
    Article.objects.all().update(status="approved")


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0006_alter_article_hero_image_alter_articleimage_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="status",
            field=models.CharField(
                verbose_name="Status",
                choices=[
                    ("pending", "Pending Review"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.RunPython(approve_existing_articles, migrations.RunPython.noop),
    ]
