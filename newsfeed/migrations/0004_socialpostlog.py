from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0003_rating_panel_site_update"),
    ]

    operations = [
        migrations.CreateModel(
            name="SocialPostLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("platform", models.CharField(choices=[("telegram", "Telegram")], db_index=True, max_length=30)),
                ("event_key", models.CharField(db_index=True, max_length=200)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")], db_index=True, default="pending", max_length=20)),
                ("target_url", models.CharField(blank=True, max_length=500)),
                ("message", models.TextField(blank=True)),
                ("response", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Social post log",
                "verbose_name_plural": "Social post logs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="socialpostlog",
            constraint=models.UniqueConstraint(fields=("platform", "event_key"), name="unique_social_post_event"),
        ),
    ]
