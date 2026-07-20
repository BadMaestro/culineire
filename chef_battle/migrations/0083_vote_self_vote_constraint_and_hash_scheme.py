"""Enforce "a chef cannot vote for themselves" in the database, and label
which recipe produced each stored request fingerprint.

Two things happen here, both about votes that already exist on production.

1. `voter_author` is added and backfilled from RecipeAuthor.user before the
   CheckConstraint is created. Adding the constraint first would fail on any
   historical self-vote; backfilling first means such a row is found rather
   than hidden, and the migration stops with the id in the error.

2. `hash_scheme` marks existing rows as v1 (bare SHA-256) while new rows
   default to v2 (HMAC). Existing hashes cannot be recomputed — the IP and user
   agent that produced them were never stored — so they are labelled, not
   rewritten, and the fraud gates compare only within one label.
"""
from django.db import migrations, models
import django.db.models.deletion


def backfill_voter_author(apps, schema_editor):
    BattleVote = apps.get_model("chef_battle", "BattleVote")
    RecipeAuthor = apps.get_model("recipes", "RecipeAuthor")

    author_by_user = dict(
        RecipeAuthor.objects.exclude(user__isnull=True).values_list("user_id", "id")
    )
    updated = []
    for vote in BattleVote.objects.exclude(voter__isnull=True).only("id", "voter_id"):
        author_id = author_by_user.get(vote.voter_id)
        if author_id is not None:
            vote.voter_author_id = author_id
            updated.append(vote)
    BattleVote.objects.bulk_update(updated, ["voter_author"], batch_size=500)

    # If any historical row is a self-vote the constraint below cannot be
    # created. Report it by id instead of letting the database raise an opaque
    # constraint error with no row in it.
    offenders = list(
        BattleVote.objects.filter(voter_author_id=models.F("voted_for_id"))
        .values_list("id", flat=True)[:20]
    )
    if offenders:
        raise RuntimeError(
            "Existing self-votes block the new constraint. "
            f"BattleVote ids: {offenders}. Decide with the owner whether to "
            "delete them or reassign, then re-run this migration."
        )


def unbackfill(apps, schema_editor):
    """Reverse leaves the column to be dropped by the AddField reversal."""


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0001_initial"),
        ("chef_battle", "0082_clarify_theme_recipe_help_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="battlevote",
            name="voter_author",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="battle_votes_cast",
                to="recipes.recipeauthor",
            ),
        ),
        # Added with the legacy label so rows that predate this migration keep
        # an honest description of how their hashes were made, then the column
        # default is switched so new rows say v2.
        migrations.AddField(
            model_name="battlevote",
            name="hash_scheme",
            field=models.CharField(db_index=True, default="v1", max_length=8),
        ),
        migrations.AddField(
            model_name="voteintegrityevent",
            name="hash_scheme",
            field=models.CharField(db_index=True, default="v1", max_length=8),
        ),
        migrations.AlterField(
            model_name="battlevote",
            name="hash_scheme",
            field=models.CharField(db_index=True, default="v2", max_length=8),
        ),
        migrations.AlterField(
            model_name="voteintegrityevent",
            name="hash_scheme",
            field=models.CharField(db_index=True, default="v2", max_length=8),
        ),
        migrations.RunPython(backfill_voter_author, unbackfill),
        migrations.AddConstraint(
            model_name="battlevote",
            constraint=models.CheckConstraint(
                condition=models.Q(("voter_author", models.F("voted_for")), _negated=True),
                name="chef_cannot_vote_for_themselves",
            ),
        ),
    ]
