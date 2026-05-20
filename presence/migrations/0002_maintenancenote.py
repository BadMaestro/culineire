from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("presence", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MaintenanceNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(blank=True, max_length=40)),
                ("message", models.CharField(max_length=240)),
                ("ip_hash", models.CharField(blank=True, db_index=True, max_length=64)),
                ("user_agent", models.CharField(blank=True, max_length=180)),
                ("is_visible", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="replies",
                        to="presence.maintenancenote",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
