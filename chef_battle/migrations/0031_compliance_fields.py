from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0030_chefartifact_extended_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="chefbattleprofile",
            name="payout_blocked",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Payout blocked pending compliance review",
            ),
        ),
        migrations.AddField(
            model_name="appreciationgift",
            name="is_flagged",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Flagged for compliance review",
            ),
        ),
        migrations.AlterField(
            model_name="ledgerevent",
            name="event_type",
            field=models.CharField(
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
                    ("admin_note", "Admin Note"),
                    ("artifact_granted", "Artifact Granted (Admin)"),
                    ("chargeback_lock", "Chargeback Lock"),
                    ("content_report", "Content Report"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
