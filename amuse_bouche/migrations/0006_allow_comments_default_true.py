from django.db import migrations, models


def enable_comments_on_all(apps, schema_editor):
    """Enable comments on all existing items (they were off only due to old default)."""
    AmuseBouche = apps.get_model("amuse_bouche", "AmuseBouche")
    AmuseBouche.objects.filter(allow_comments=False).update(allow_comments=True)


class Migration(migrations.Migration):

    dependencies = [
        ("amuse_bouche", "0005_amusebouchecomment_parent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="amusebouche",
            name="allow_comments",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(enable_comments_on_all, migrations.RunPython.noop),
    ]
