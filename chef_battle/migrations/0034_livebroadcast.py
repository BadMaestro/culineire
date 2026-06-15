from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0033_phase10_livestream"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LiveBroadcast",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("recording_reference", models.CharField(blank=True, max_length=300)),
                (
                    "moderation_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Review"),
                            ("approved", "Approved for Publication"),
                            ("rejected", "Rejected"),
                            ("under_review", "Under Review"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("safety_delay_enabled", models.BooleanField(default=True, help_text="30-60s broadcast delay applied")),
                ("stopped_by_staff", models.BooleanField(default=False)),
                ("stop_reason", models.CharField(blank=True, max_length=300)),
                ("report_count", models.PositiveIntegerField(default=0)),
                ("moderation_note", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "session",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="broadcast",
                        to="chef_battle.livestreamsession",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_broadcasts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="LiveBroadcastReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("child_safety", "Child Safety"),
                            ("privacy_breach", "Privacy Breach"),
                            ("prohibited_content", "Prohibited Content"),
                            ("alcohol_drug", "Alcohol / Drug Misuse"),
                            ("illegal_content", "Illegal Content"),
                            ("copyright", "Copyright Breach"),
                            ("other", "Other"),
                        ],
                        db_index=True,
                        max_length=24,
                    ),
                ),
                ("description", models.CharField(blank=True, max_length=500)),
                ("reported_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "broadcast",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reports",
                        to="chef_battle.livebroadcast",
                    ),
                ),
                (
                    "reporter",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="live_broadcast_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-reported_at"]},
        ),
    ]
