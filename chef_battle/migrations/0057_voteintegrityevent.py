# Generated manually for P06 vote-integrity evidence.

from django.db import migrations, models
import django.db.models.deletion
import chef_battle.models


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0056_battle_paused_at_battle_paused_from_status_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="VoteIntegrityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("gate_code", models.CharField(db_index=True, max_length=40)),
                ("failed_gates", models.JSONField(blank=True, default=list)),
                ("is_authenticated", models.BooleanField(default=False)),
                ("ip_hash", models.CharField(blank=True, max_length=64)),
                ("user_agent_hash", models.CharField(blank=True, max_length=64)),
                ("session_key_hash", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("expires_at", models.DateTimeField(db_index=True, default=chef_battle.models.vote_integrity_expires_at)),
                ("battle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vote_integrity_events", to="chef_battle.battle")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["battle", "-created_at"], name="vote_int_battle_time_idx")],
            },
        ),
    ]
