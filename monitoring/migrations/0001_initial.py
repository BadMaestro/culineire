import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PageView",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("path", models.CharField(db_index=True, max_length=500)),
                ("referrer", models.CharField(blank=True, max_length=500)),
                ("session_key", models.CharField(blank=True, db_index=True, max_length=40)),
                ("ip_hash", models.CharField(blank=True, max_length=64)),
                ("user_agent", models.CharField(blank=True, max_length=200)),
                ("status_code", models.PositiveSmallIntegerField(default=200)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="page_views",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"verbose_name": "Page view", "verbose_name_plural": "Page views", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="UserActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.CharField(blank=True, max_length=40)),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("login", "Login"),
                            ("logout", "Logout"),
                            ("register", "Register"),
                            ("profile_update", "Profile Update"),
                            ("recipe_view", "Recipe View"),
                            ("article_view", "Article View"),
                            ("comment", "Comment"),
                            ("failed_login", "Failed Login"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                ("object_type", models.CharField(blank=True, max_length=50)),
                ("object_id", models.PositiveIntegerField(blank=True, null=True)),
                ("object_title", models.CharField(blank=True, max_length=255)),
                ("ip_hash", models.CharField(blank=True, max_length=64)),
                ("path", models.CharField(blank=True, max_length=500)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"verbose_name": "User activity", "verbose_name_plural": "User activities", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SecurityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("failed_login", "Failed Login"),
                            ("suspicious_request", "Suspicious Request"),
                            ("404", "404 Not Found"),
                            ("403", "403 Forbidden"),
                            ("rate_limited", "Rate Limited"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                ("ip_hash", models.CharField(blank=True, max_length=64)),
                ("path", models.CharField(blank=True, max_length=500)),
                ("user_agent", models.CharField(blank=True, max_length=300)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="security_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"verbose_name": "Security event", "verbose_name_plural": "Security events", "ordering": ["-created_at"]},
        ),
    ]
