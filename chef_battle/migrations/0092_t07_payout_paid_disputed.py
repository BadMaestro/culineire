from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0091_f59_payout_processing_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payoutrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending Review"),
                    ("under_review", "Under Review"),
                    ("approved", "Approved"),
                    ("processing", "Processing (Stripe transfer in flight)"),
                    ("rejected", "Rejected"),
                    ("on_hold", "On Hold — Compliance"),
                    ("paid", "Paid Out"),
                    ("paid_disputed", "Paid — Reconciliation Required"),
                    ("reversed", "Reversed"),
                ],
                db_index=True,
                default="pending",
                max_length=16,
            ),
        ),
    ]
