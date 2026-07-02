from django.db import migrations, models


RANK_THRESHOLDS = (
    (700, "culinary_master"),
    (600, "executive_chef"),
    (500, "head_chef"),
    (400, "sous_chef"),
    (300, "chef_de_partie"),
    (200, "commis_chef"),
    (100, "prep_cook"),
    (0, "kitchen_porter"),
)


def rebase_ratings(apps, schema_editor):
    ChefBattleProfile = apps.get_model("chef_battle", "ChefBattleProfile")
    profiles = ChefBattleProfile.objects.filter(is_executive=False)
    for profile in profiles.iterator():
        profile.rating = max(0, profile.rating - 1000)
        profile.rank = next(
            rank for threshold, rank in RANK_THRESHOLDS if profile.rating >= threshold
        )
        profile.save(update_fields=["rating", "rank"])


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0050_alter_chefbattleprofile_rank"),
    ]

    operations = [
        migrations.RunPython(rebase_ratings, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="chefbattleprofile",
            name="rating",
            field=models.IntegerField(db_index=True, default=0),
        ),
    ]
