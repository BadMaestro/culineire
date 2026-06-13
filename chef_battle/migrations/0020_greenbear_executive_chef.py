from django.conf import settings
from django.db import migrations


def set_greenbear_executive_chef(apps, schema_editor):
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")
    ChefBattleProfile = apps.get_model("chef_battle", "ChefBattleProfile")
    try:
        owner = RecipeAuthor.objects.get(slug=settings.OWNER_SLUG)
        profile, _ = ChefBattleProfile.objects.get_or_create(author=owner)
        profile.prestige_title = "executive_chef"
        profile.save(update_fields=["prestige_title"])
    except RecipeAuthor.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0019_prestige_executive_chef"),
    ]

    operations = [
        migrations.RunPython(set_greenbear_executive_chef, migrations.RunPython.noop),
    ]
