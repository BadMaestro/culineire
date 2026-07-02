from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0051_rebase_chef_rating_system"),
    ]

    operations = [
        migrations.AddField(
            model_name="battle",
            name="challenger_ready",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="battle",
            name="opponent_ready",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="battle",
            name="proposed_combat_time",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="battle",
            name="combat_time_confirmed",
            field=models.BooleanField(default=False),
        ),
    ]
