from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("articles", "0007_article_status"),
        ("recipes", "0016_rename_gender_to_default_avatar"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reporter_name", models.CharField(max_length=100, verbose_name="Your name")),
                ("reporter_email", models.EmailField(max_length=254, verbose_name="Your email")),
                ("report_type", models.CharField(
                    choices=[
                        ("copyright", "Copyright infringement"),
                        ("watermark", "Watermarked or unlicensed image"),
                        ("inaccurate_credit", "Inaccurate or missing credit"),
                        ("stolen_recipe", "Stolen or uncredited recipe"),
                        ("other", "Other"),
                    ],
                    default="copyright",
                    max_length=30,
                    verbose_name="Type of issue",
                )),
                ("reported_url", models.CharField(blank=True, max_length=500, verbose_name="URL of the content in question")),
                ("description", models.TextField(
                    help_text="Please describe the issue clearly. Include the original source if applicable.",
                    max_length=2000,
                    verbose_name="Description",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_resolved", models.BooleanField(default=False, verbose_name="Resolved")),
                ("resolved_note", models.CharField(blank=True, max_length=500, verbose_name="Resolution note")),
                ("recipe", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="content_reports",
                    to="recipes.recipe",
                    verbose_name="Reported recipe",
                )),
                ("article", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="content_reports",
                    to="articles.article",
                    verbose_name="Reported article",
                )),
            ],
            options={
                "verbose_name": "Content report",
                "verbose_name_plural": "Content reports",
                "ordering": ["-created_at"],
            },
        ),
    ]
