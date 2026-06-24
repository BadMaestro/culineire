from django.db import migrations


def set_level(apps, schema_editor):
    ChefBattleProfile = apps.get_model("chef_battle", "ChefBattleProfile")
    profile = ChefBattleProfile.objects.filter(author__name__icontains="jam").first()
    if profile is None:
        profile = ChefBattleProfile.objects.filter(author__slug__icontains="jam").first()
    if profile is None:
        return
    profile.level = 4
    profile.wins = 12
    profile.save(update_fields=["level", "wins", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("chef_battle", "0040_jam_oliver_energy"),
    ]

    operations = [
        migrations.RunPython(set_level, migrations.RunPython.noop),
    ]
