from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0007_article_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
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
        migrations.AddField(
            model_name="article",
            name="image_rights_note",
            field=models.CharField(
                "Image rights note",
                blank=True,
                help_text="Credit line or permission reference if any.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="article",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("original", "Original writing"),
                    ("adapted", "Adapted from a source"),
                    ("inspired", "Inspired by a source"),
                ],
                default="original",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="article",
            name="source_title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="article",
            name="source_author",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="article",
            name="source_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="article",
            name="source_note",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="article",
            name="confirmed_own_work",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="article",
            name="confirmed_image_rights",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="article",
            name="confirmed_rules",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="article",
            name="confirmation_timestamp",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="article",
            name="confirmed_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="confirmed_articles",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
