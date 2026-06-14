from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0026_update_appreciation_gift_types"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # --- ChefBattleProfile: 18+ compliance + fraud flags ---
        migrations.AddField(
            model_name="chefbattleprofile",
            name="age_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="chefbattleprofile",
            name="age_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chefbattleprofile",
            name="is_suspended",
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name="chefbattleprofile",
            name="suspended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chefbattleprofile",
            name="suspension_reason",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="chefbattleprofile",
            name="fraud_flag",
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name="chefbattleprofile",
            name="fraud_flag_note",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="chefbattleprofile",
            name="dsa_reported_count",
            field=models.PositiveIntegerField(default=0),
        ),
        # --- ChefArtifact: consumption tracking ---
        migrations.AddField(
            model_name="chefartifact",
            name="status",
            field=models.CharField(
                choices=[("active", "Active"), ("consumed", "Consumed")],
                db_index=True,
                default="active",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="chefartifact",
            name="consumed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chefartifact",
            name="consumed_in_battle",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="consumed_artifacts",
                to="chef_battle.battle",
            ),
        ),
        # --- RewardRecord ---
        migrations.CreateModel(
            name="RewardRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reward_type", models.CharField(
                    choices=[("cbr", "Chef Battle Reward"), ("lsr", "Live Support Reward")],
                    db_index=True,
                    max_length=8,
                )),
                ("tokens_granted", models.PositiveIntegerField()),
                ("reason", models.CharField(max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("recipient", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="reward_records",
                    to="recipes.recipeauthor",
                )),
                ("related_battle", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="reward_records",
                    to="chef_battle.battle",
                )),
                ("related_gift", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="reward_records",
                    to="chef_battle.appreciationgift",
                )),
                ("granted_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="granted_reward_records",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # --- LedgerEvent ---
        migrations.CreateModel(
            name="LedgerEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(
                    choices=[
                        ("token_purchase", "Token Purchase"),
                        ("gift_sent", "Gift Sent"),
                        ("gift_received", "Gift Received"),
                        ("battle_gift_sent", "Battle Gift Sent"),
                        ("artifact_purchased", "Artifact Purchased"),
                        ("artifact_dropped", "Artifact Dropped"),
                        ("artifact_consumed", "Artifact Consumed"),
                        ("cbr_granted", "CBR Granted"),
                        ("lsr_granted", "LSR Granted"),
                        ("refund_issued", "Refund Issued"),
                        ("challenge_created", "Challenge Created"),
                        ("challenge_accepted", "Challenge Accepted"),
                        ("challenge_refused", "Challenge Refused"),
                        ("battle_started", "Battle Started"),
                        ("battle_completed", "Battle Completed"),
                        ("vote_cast", "Vote Cast"),
                        ("rank_promoted", "Rank Promoted"),
                        ("level_up", "Level Up"),
                        ("fraud_flag", "Fraud Flag"),
                        ("account_suspended", "Account Suspended"),
                    ],
                    db_index=True,
                    max_length=32,
                )),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ledger_events_as_actor",
                    to="recipes.recipeauthor",
                )),
                ("target", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ledger_events_as_target",
                    to="recipes.recipeauthor",
                )),
                ("related_battle", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ledger_events",
                    to="chef_battle.battle",
                )),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # --- ContentReport (DSA) ---
        migrations.CreateModel(
            name="ContentReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content_kind", models.CharField(
                    choices=[
                        ("battle_chat", "Battle Chat Message"),
                        ("battle_entry", "Battle Entry"),
                        ("chef_profile", "Chef Profile"),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ("object_id", models.PositiveIntegerField()),
                ("reason", models.CharField(max_length=300)),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending Review"),
                        ("reviewed", "Reviewed"),
                        ("actioned", "Actioned"),
                        ("dismissed", "Dismissed"),
                    ],
                    db_index=True,
                    default="pending",
                    max_length=12,
                )),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("moderator_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("reporter", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="content_reports",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("reviewed_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="reviewed_content_reports",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
