"""T11, Owner ruling 2026-08-15: the Stage 1 winner shoots at the loser's
DECLARED menu, not at the text lines of his submitted recipe.

Three changes, and one deliberate deletion of data.

IngredientLock goes entirely. Its whole purpose was the loser placing two
locks AFTER he had already lost; under the Owner's ruling both chefs block
exactly two ingredients BEFORE Stage 1, and they do it through declare_menu as
BattleIngredient.is_key (KEY_COUNT = 2). Keeping a second lock table beside it
would leave two answers to "is this ingredient protected".

IngredientShot.target_index (a line number in recipe TEXT) becomes
target_ingredient, a foreign key to the BattleIngredient row itself - the same
row round combat eliminates.

THE OLD ROWS ARE DELETED RATHER THAN BACKFILLED, and the reason is checked
against production rather than assumed. Measured on production 2026-08-15
before writing this: 2 IngredientLock rows and 3 IngredientShot rows exist,
all five belong to battle 14, which is COMPLETED, and both its chefs are the
emulation bots (emu-chef-alpha, emu-chef-beta). Zero battles are in
INGREDIENT_PENALTY, so no live biathlon is interrupted. There is also nothing
to backfill INTO: production carries zero BattleIngredient rows, because the
emulator never actually declared a menu - it said it did in its own note and
submitted entries instead, which is fixed in this same change. No real chef's
history, no money, no audit chain: a rehearsal bout's leftovers.
"""

from django.db import migrations, models
import django.db.models.deletion


def drop_superseded_shots(apps, schema_editor):
    """Remove shots aimed at recipe-text indices, which no longer mean anything."""
    IngredientShot = apps.get_model("chef_battle", "IngredientShot")
    IngredientShot.objects.all().delete()


def noop_reverse(apps, schema_editor):
    """Reversing restores the columns, not the rows.

    The deleted rows pointed into a coordinate space (recipe text line
    numbers) that the forward migration abolishes; inventing replacements on
    the way back would be fabricating history rather than restoring it.
    """
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0097_t19_challenge_task_kind"),
    ]

    operations = [
        migrations.RunPython(drop_superseded_shots, noop_reverse),
        migrations.AddField(
            model_name="battle",
            name="ingredient_penalty_deadline",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.RemoveField(
            model_name="ingredientshot",
            name="target_index",
        ),
        migrations.AddField(
            model_name="ingredientshot",
            name="target_ingredient",
            field=models.ForeignKey(
                default=None,
                help_text="The loser's declared ingredient this shot was aimed at.",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="shots",
                to="chef_battle.battleingredient",
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="ingredientshot",
            name="bounced",
            field=models.BooleanField(
                default=False,
                help_text="True if the shot hit a key ingredient and bounced",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="ingredientlock",
            name="unique_lock_per_ingredient",
        ),
        migrations.DeleteModel(
            name="IngredientLock",
        ),
    ]
