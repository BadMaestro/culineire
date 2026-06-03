from django.db import migrations
from django.utils import timezone


def approve_owner_pending(apps, schema_editor):
    AmuseBouche = apps.get_model("amuse_bouche", "AmuseBouche")
    now = timezone.now()
    AmuseBouche.objects.filter(
        status="pending",
        author__slug="greenbear",
    ).update(
        status="approved",
        published_at=now,
        moderated_at=now,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("amuse_bouche", "0007_add_image_rights_and_confirmations"),
    ]

    operations = [
        migrations.RunPython(approve_owner_pending, migrations.RunPython.noop),
    ]
