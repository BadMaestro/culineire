from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chef_battle', '0067_pinch_published_txtype'),
    ]

    operations = [
        migrations.AddField(
            model_name='battlecombataction',
            name='target_ingredient',
            field=models.ForeignKey(
                blank=True,
                help_text="Opponent ingredient this attack targets (attack only; ignored on defend).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='targeted_by_actions',
                to='chef_battle.battleingredient',
            ),
        ),
    ]
