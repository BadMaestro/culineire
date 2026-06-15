from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0032_phase9_payouts"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LiveStreamSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "provider",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "Not configured"),
                            ("mux", "Mux"),
                            ("agora", "Agora"),
                            ("livekit", "LiveKit"),
                            ("other", "Other"),
                        ],
                        default="",
                        max_length=16,
                    ),
                ),
                ("provider_stream_id", models.CharField(blank=True, db_index=True, max_length=200)),
                ("provider_playback_url", models.URLField(blank=True, max_length=500)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("scheduled", "Scheduled"),
                            ("live", "Live"),
                            ("ended", "Ended"),
                            ("terminated", "Terminated by Platform"),
                            ("failed", "Failed / Technical Error"),
                        ],
                        db_index=True,
                        default="scheduled",
                        max_length=12,
                    ),
                ),
                ("checklist_confirmed", models.BooleanField(default=False)),
                ("checklist_confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("terminated_reason", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "battle",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="live_streams",
                        to="chef_battle.battle",
                    ),
                ),
                (
                    "chef",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="live_stream_sessions",
                        to="recipes.recipeauthor",
                    ),
                ),
                (
                    "terminated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="terminated_streams",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
