import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0016_rename_gender_to_default_avatar"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="recipe",
            name="confirmed_own_work",
            field=models.BooleanField(default=False, verbose_name="Confirmed: original or properly credited work"),
        ),
        migrations.AddField(
            model_name="recipe",
            name="confirmed_image_rights",
            field=models.BooleanField(default=False, verbose_name="Confirmed: image rights"),
        ),
        migrations.AddField(
            model_name="recipe",
            name="confirmed_rules",
            field=models.BooleanField(default=False, verbose_name="Confirmed: content publishing rules"),
        ),
        migrations.AddField(
            model_name="recipe",
            name="confirmation_timestamp",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Confirmed at"),
        ),
        migrations.AddField(
            model_name="recipe",
            name="confirmed_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="confirmed_recipes",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Confirmed by",
            ),
        ),
        migrations.AddField(
            model_name="recipe",
            name="image_rights_status",
            field=models.CharField(
                choices=[
                    ("own", "My own photo"),
                    ("licensed", "Licensed (CC, stock, written permission)"),
                    ("public_domain", "Public domain"),
                    ("not_applicable", "No image uploaded"),
                ],
                default="not_applicable",
                max_length=20,
                verbose_name="Image rights",
            ),
        ),
        migrations.AddField(
            model_name="recipe",
            name="image_rights_note",
            field=models.CharField(
                blank=True,
                help_text="Optional: licence name, credit line, or permission reference.",
                max_length=255,
                verbose_name="Image rights note",
            ),
        ),
    ]
