from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sponsors", "0012_alter_sponsorauditlog_action_sponsorsanctionsmatch"),
    ]

    operations = [
        migrations.AddField(
            model_name="sponsorcell",
            name="price_override_cents",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text="Per-cell price override in cents. Overrides RING_PRICES when set.",
            ),
        ),
    ]
