from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0034_livebroadcast"),
    ]

    operations = [
        migrations.CreateModel(
            name="LiveBattleAgreement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("accepted_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("agreement_version", models.CharField(default="1.0", max_length=20)),
                ("consent_text_snapshot", models.TextField(help_text="Full agreement text shown to chef, frozen for audit")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                (
                    "chef",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="live_battle_agreements",
                        to="recipes.recipeauthor",
                    ),
                ),
            ],
            options={"ordering": ["-accepted_at"]},
        ),
    ]
