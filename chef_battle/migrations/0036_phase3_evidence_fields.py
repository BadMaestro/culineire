from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0035_livebattleagreement"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # New moderation statuses are TextChoices — no DB change needed for the field itself,
        # but we add the new fields: real_photo_confirmed, photo_hash, moderation_note,
        # reviewed_by, reviewed_at.
        migrations.AddField(
            model_name="battleentry",
            name="real_photo_confirmed",
            field=models.BooleanField(
                default=False,
                help_text="Chef confirmed cooked photo is a real photograph (\xa732)",
            ),
        ),
        migrations.AddField(
            model_name="battleentry",
            name="photo_hash",
            field=models.CharField(
                blank=True,
                max_length=64,
                help_text="SHA-256 of cooked_photo for duplicate detection",
            ),
        ),
        migrations.AddField(
            model_name="battleentry",
            name="moderation_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="battleentry",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_battle_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="battleentry",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Expand moderation_status max_length to fit new statuses (suspected_stock = 15 chars)
        migrations.AlterField(
            model_name="battleentry",
            name="moderation_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("flagged", "Flagged"),
                    ("needs_changes", "Needs Changes"),
                    ("suspected_ai", "Suspected AI Image"),
                    ("suspected_stock", "Suspected Stock Photo"),
                    ("duplicate", "Duplicate Image"),
                ],
                db_index=True,
                default="pending",
                max_length=16,
            ),
        ),
    ]
