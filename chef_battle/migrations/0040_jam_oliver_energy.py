from django.db import migrations


def add_energy(apps, schema_editor):
    ChefBattleProfile = apps.get_model("chef_battle", "ChefBattleProfile")
    BattleMoveTransaction = apps.get_model("chef_battle", "BattleMoveTransaction")

    profile = (
        ChefBattleProfile.objects.filter(author__name__icontains="jam")
        .first()
    )
    if profile is None:
        profile = (
            ChefBattleProfile.objects.filter(author__slug__icontains="jam")
            .first()
        )
    if profile is None:
        return

    profile.battle_moves = min(100, profile.battle_moves + 100)
    profile.save(update_fields=["battle_moves", "updated_at"])

    BattleMoveTransaction.objects.create(
        chef=profile.author,
        amount=100,
        transaction_type="admin_adjustment",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("chef_battle", "0039_remove_article_battle_type"),
    ]

    operations = [
        migrations.RunPython(add_energy, migrations.RunPython.noop),
    ]
