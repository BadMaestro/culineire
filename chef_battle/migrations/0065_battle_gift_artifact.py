from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chef_battle', '0061_surviving_ingredients_and_artifact_used'),
    ]

    operations = [
        # Add BATTLE_GIFT to source choices (no DB change, just state)
        migrations.AlterField(
            model_name='chefartifact',
            name='source',
            field=models.CharField(
                choices=[
                    ('purchased', 'Purchased'),
                    ('gifted', 'Gifted'),
                    ('drop', 'Battle Drop'),
                    ('admin_grant', 'Admin Grant'),
                    ('battle_gift', 'Battle Gift (in-battle delivery)'),
                ],
                default='purchased',
                max_length=16,
            ),
        ),
        # Add locked_to_battle FK
        migrations.AddField(
            model_name='chefartifact',
            name='locked_to_battle',
            field=models.ForeignKey(
                blank=True,
                help_text='Battle-gift artifact: must be used in this battle, expires unused when battle ends.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='battle_gift_artifacts',
                to='chef_battle.battle',
            ),
        ),
        # Remove unique_artifact_per_chef constraint
        migrations.RemoveConstraint(
            model_name='chefartifact',
            name='unique_artifact_per_chef',
        ),
        # Add delivery_fee to ViewerBattleGift
        migrations.AddField(
            model_name='viewerbattlegift',
            name='delivery_fee',
            field=models.PositiveIntegerField(
                default=0,
                help_text='In-battle delivery fee (equals artifact cost).',
            ),
        ),
    ]
