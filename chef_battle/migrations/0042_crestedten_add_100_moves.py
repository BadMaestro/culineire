from django.db import migrations


def add_moves(apps, schema_editor):
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")
    ChefBattleProfile = apps.get_model("chef_battle", "ChefBattleProfile")
    try:
        author = RecipeAuthor.objects.get(slug="crestedten")
        profile = ChefBattleProfile.objects.get(author=author)
        profile.battle_moves += 100
        profile.save()
    except (RecipeAuthor.DoesNotExist, ChefBattleProfile.DoesNotExist):
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0041_add_enrolled_at_field"),
    ]

    operations = [
        migrations.RunPython(add_moves, migrations.RunPython.noop),
    ]
