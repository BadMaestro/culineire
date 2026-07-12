from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Originally created by GreenBear session 2026-07-10 (server-only, never pushed to git).
    Recovered as a stub — already applied to production DB.
    Adds chest_moves overflow field to ChefBattleProfile.
    """

    dependencies = [
        ('chef_battle', '0061_surviving_ingredients_and_artifact_used'),
    ]

    operations = [
        migrations.AddField(
            model_name='chefbattleprofile',
            name='chest_moves',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Overflow moves stored in the chest when wallet is full.',
            ),
        ),
    ]
