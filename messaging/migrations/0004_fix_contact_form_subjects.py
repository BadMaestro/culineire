from django.db import migrations


def fix_contact_subjects(apps, _schema_editor):
    message_model = apps.get_model("messaging", "Message")
    message_model.objects.filter(
        parent=None,
        subject="Contact form message",
    ).update(subject="Message from CulinEire Kitchen Author")


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0003_fix_moderation_subjects"),
    ]

    operations = [
        migrations.RunPython(fix_contact_subjects, migrations.RunPython.noop),
    ]
