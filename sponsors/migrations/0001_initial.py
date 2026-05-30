from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SponsorCell",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "cell_number",
                    models.PositiveIntegerField(
                        db_index=True,
                        unique=True,
                    ),
                ),
                (
                    "ring",
                    models.PositiveIntegerField(
                        db_index=True,
                        help_text="0 = centre (CulinEire logo), 1 = inner, 4 = outer",
                    ),
                ),
                ("position_in_ring", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("available", "Available"),
                            ("reserved", "Reserved"),
                            ("sold", "Sold"),
                        ],
                        db_index=True,
                        default="available",
                        max_length=20,
                    ),
                ),
                ("sponsor_name", models.CharField(blank=True, max_length=200)),
                (
                    "sponsor_logo",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="sponsors/logos/",
                    ),
                ),
                ("sponsor_url", models.URLField(blank=True)),
                ("sponsor_tagline", models.CharField(blank=True, max_length=200)),
                ("purchased_at", models.DateTimeField(blank=True, null=True)),
                ("admin_notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Sponsor Cell",
                "verbose_name_plural": "Sponsor Cells",
                "ordering": ["ring", "position_in_ring"],
            },
        ),
    ]
