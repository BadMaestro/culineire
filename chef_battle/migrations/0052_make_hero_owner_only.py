from django.db import migrations


def make_hero_owner_only(apps, schema_editor):
    ChefBattleProfile = apps.get_model("chef_battle", "ChefBattleProfile")
    ChefBattleProfile.objects.exclude(author__slug="greenbear").update(
        is_hero=False,
        level=1,
    )
    ChefBattleProfile.objects.filter(author__slug="greenbear").update(
        is_hero=True,
        infinite_moves=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0051_rebase_chef_rating_system"),
    ]

    operations = [
        migrations.RunPython(make_hero_owner_only, migrations.RunPython.noop),
    ]
