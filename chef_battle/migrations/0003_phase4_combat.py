from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0002_add_missing_fields_phase0"),
        ("recipes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BattleCombatAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("round_number", models.PositiveSmallIntegerField()),
                ("action_type", models.CharField(choices=[("attack", "Attack"), ("defend", "Defend")], max_length=8)),
                ("moves_invested", models.PositiveSmallIntegerField(default=1)),
                ("is_locked", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("battle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="combat_actions", to="chef_battle.battle")),
                ("chef", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="combat_actions", to="recipes.recipeauthor")),
            ],
            options={"ordering": ["round_number", "created_at"]},
        ),
        migrations.AddConstraint(
            model_name="battlecombataction",
            constraint=models.UniqueConstraint(
                fields=["battle", "chef", "round_number"],
                name="unique_combat_action_per_chef_per_round",
            ),
        ),
        migrations.CreateModel(
            name="BattleRound",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("round_number", models.PositiveSmallIntegerField()),
                ("attack_power", models.PositiveSmallIntegerField()),
                ("defence_power", models.PositiveSmallIntegerField()),
                ("outcome", models.CharField(choices=[("full_hit", "Full Hit"), ("partial_hit", "Partial Hit"), ("blocked", "Blocked"), ("draw", "Draw")], max_length=12)),
                ("challenger_hits", models.PositiveSmallIntegerField(default=0)),
                ("opponent_hits", models.PositiveSmallIntegerField(default=0)),
                ("log_message", models.CharField(blank=True, max_length=300)),
                ("resolved_at", models.DateTimeField(auto_now_add=True)),
                ("attacker", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attack_rounds", to="recipes.recipeauthor")),
                ("battle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="combat_rounds", to="chef_battle.battle")),
                ("defender", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="defence_rounds", to="recipes.recipeauthor")),
            ],
            options={"ordering": ["round_number"]},
        ),
        migrations.AddConstraint(
            model_name="battleround",
            constraint=models.UniqueConstraint(
                fields=["battle", "round_number"],
                name="unique_round_per_battle",
            ),
        ),
    ]
