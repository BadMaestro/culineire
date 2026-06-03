from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("amuse_bouche", "0008_approve_greenbear_pending"),
    ]

    operations = [
        migrations.AddField(
            model_name="amusebouche",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("original", "Original"),
                    ("ai_assisted", "AI assisted"),
                    ("family", "Family recipe"),
                    ("cookbook", "Cookbook"),
                    ("website", "Website"),
                    ("restaurant", "Restaurant"),
                    ("other", "Other"),
                ],
                default="original",
                max_length=20,
                verbose_name="Source type",
            ),
        ),
        migrations.AddField(
            model_name="amusebouche",
            name="source_title",
            field=models.CharField(blank=True, max_length=255, verbose_name="Source title"),
        ),
        migrations.AddField(
            model_name="amusebouche",
            name="source_author",
            field=models.CharField(blank=True, max_length=255, verbose_name="Source author"),
        ),
        migrations.AddField(
            model_name="amusebouche",
            name="source_url",
            field=models.URLField(blank=True, verbose_name="Source URL"),
        ),
        migrations.AddField(
            model_name="amusebouche",
            name="source_note",
            field=models.TextField(blank=True, verbose_name="Source note"),
        ),
    ]
