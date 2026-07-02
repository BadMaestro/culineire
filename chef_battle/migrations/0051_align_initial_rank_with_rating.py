from django.db import migrations, models


RANK_THRESHOLDS = (
    (1800, "culinary_master"),
    (1600, "executive_chef"),
    (1450, "head_chef"),
    (1300, "sous_chef"),
    (1180, "chef_de_partie"),
    (1080, "commis_chef"),
    (1000, "prep_cook"),
)


def align_kitchen_porter_ranks(apps, schema_editor):
    ChefBattleProfile = apps.get_model("chef_battle", "ChefBattleProfile")
    stale_profiles = ChefBattleProfile.objects.filter(
        rank="kitchen_porter",
        rating__gte=1000,
        is_executive=False,
    )
    for profile in stale_profiles.iterator():
        profile.rank = next(
            rank for threshold, rank in RANK_THRESHOLDS if profile.rating >= threshold
        )
        profile.save(update_fields=["rank"])


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0050_alter_chefbattleprofile_rank"),
    ]

    operations = [
        migrations.RunPython(align_kitchen_porter_ranks, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="chefbattleprofile",
            name="rank",
            field=models.CharField(
                choices=[
                    ("kitchen_porter", "Kitchen Porter"),
                    ("prep_cook", "Prep Chef"),
                    ("commis_chef", "Commis Chef"),
                    ("chef_de_partie", "Chef de Partie"),
                    ("sous_chef", "Sous Chef"),
                    ("head_chef", "Head Chef"),
                    ("executive_chef", "Executive Chef"),
                    ("culinary_master", "Culinary Master"),
                ],
                default="prep_cook",
                max_length=32,
            ),
        ),
    ]
