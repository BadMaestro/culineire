from django.db import migrations


class Migration(migrations.Migration):
    """
    Stub — recovered from server DB (GreenBear session 2026-07-10, never pushed).
    Original added ENROL_BONUS to BattleMoveTransaction.TxType choices.
    Choices are code-only in Django TextField — no DB operation needed.
    """

    dependencies = [
        ('chef_battle', '0062_chest_moves_field'),
    ]

    operations = [
    ]
