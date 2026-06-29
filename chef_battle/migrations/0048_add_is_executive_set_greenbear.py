from django.db import migrations, models


def set_greenbear_executive(apps, schema_editor):
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")
    ChefBattleProfile = apps.get_model("chef_battle", "ChefBattleProfile")
    author = RecipeAuthor.objects.filter(slug="greenbear").first()
    if author:
        ChefBattleProfile.objects.filter(author=author).update(is_executive=True)


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0047_fix_crestedten_moves_and_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="chefbattleprofile",
            name="is_executive",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Executive role — excluded from chef rankings and battle participation",
            ),
        ),
        migrations.RunPython(set_greenbear_executive, migrations.RunPython.noop),
    ]
