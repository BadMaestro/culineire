import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NewsFeedEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "entry_type",
                    models.CharField(
                        choices=[
                            ("recipe_published", "Recipe Published"),
                            ("article_published", "Article Published"),
                            ("site_update", "Site Update"),
                            ("security_update", "Security Update"),
                            ("version_release", "Version Release"),
                            ("admin_note", "Admin Note"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                ("title", models.CharField(max_length=300)),
                ("message", models.TextField(blank=True)),
                ("url", models.CharField(blank=True, max_length=500)),
                ("published_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("is_auto", models.BooleanField(default=False)),
                ("is_public", models.BooleanField(default=True)),
                ("version", models.CharField(blank=True, max_length=30)),
                (
                    "event_key",
                    models.CharField(blank=True, max_length=200, null=True, unique=True),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="newsfeed_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "News Feed Entry",
                "verbose_name_plural": "News Feed Entries",
                "ordering": ["-published_at"],
            },
        ),
    ]
