from django.db import migrations


def fix_crestedten(apps, schema_editor):
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")
    ChefBattleProfile = apps.get_model("chef_battle", "ChefBattleProfile")
    try:
        author = RecipeAuthor.objects.get(slug="dmitrij-golovin")
        profile = ChefBattleProfile.objects.get(author=author)
        profile.battle_moves = profile.battle_moves + 100
        profile.level = 1
        profile.wins = 0
        profile.is_hero = False
        profile.rank = "kitchen_porter"
        profile.save(update_fields=["battle_moves", "level", "wins", "is_hero", "rank"])
    except (RecipeAuthor.DoesNotExist, ChefBattleProfile.DoesNotExist):
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0046_reset_levels_final"),
    ]

    operations = [
        migrations.RunPython(fix_crestedten, migrations.RunPython.noop),
    ]
