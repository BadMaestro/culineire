import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def delete_anonymous_votes(apps, schema_editor):
    # Owner decision 2026-07-17: anonymous visitors cannot vote. Remove the
    # historical anonymous ballots (voter IS NULL) before the column becomes
    # non-nullable. Registered votes are untouched.
    BattleVote = apps.get_model("chef_battle", "BattleVote")
    BattleVote.objects.filter(voter__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chef_battle", "0079_battle_entry_dish_submission"),
    ]

    operations = [
        migrations.RunPython(delete_anonymous_votes, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="battlevote",
            name="one_anonymous_vote_per_battle_device",
        ),
        migrations.RemoveConstraint(
            model_name="battlevote",
            name="one_authenticated_vote_per_battle",
        ),
        migrations.AlterField(
            model_name="battlevote",
            name="voter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="battle_votes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="battlevote",
            constraint=models.UniqueConstraint(
                fields=["battle", "voter"],
                name="one_authenticated_vote_per_battle",
            ),
        ),
    ]
