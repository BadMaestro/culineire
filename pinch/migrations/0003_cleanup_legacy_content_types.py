from django.db import migrations


def remove_legacy_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    legacy = ContentType.objects.filter(app_label="amuse_bouche")
    perm_ids = list(Permission.objects.filter(content_type__in=legacy).values_list("id", flat=True))
    if perm_ids:
        Permission.objects.filter(id__in=perm_ids).delete()
    legacy.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pinch", "0002_rename_tables_and_fields"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(remove_legacy_content_types, migrations.RunPython.noop),
    ]
