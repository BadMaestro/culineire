from django.db import migrations


def reset_levels(apps, schema_editor):
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")
    ChefBattleProfile = apps.get_model("chef_battle", "ChefBattleProfile")

    targets = list(RecipeAuthor.objects.filter(slug="crestedten"))
    jam = (
        RecipeAuthor.objects.filter(name__icontains="jam").first()
        or RecipeAuthor.objects.filter(slug__icontains="jam").first()
    )
    if jam:
        targets.append(jam)

    for author in targets:
        try:
            profile = ChefBattleProfile.objects.get(author=author)
            profile.level = 1
            profile.wins = 0
            profile.is_hero = False
            profile.rank = "kitchen_porter"
            profile.save(update_fields=["level", "wins", "is_hero", "rank"])
        except ChefBattleProfile.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0045_merge_migrations"),
    ]

    operations = [
        migrations.RunPython(reset_levels, migrations.RunPython.noop),
    ]
