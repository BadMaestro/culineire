from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sponsors", "0007_central_monthly_product")]

    operations = [
        migrations.AlterField(
            model_name="sponsorapplication",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("payment_pending", "Payment pending"),
                    ("paid_pending_approval", "Paid pending approval"),
                    ("changes_requested", "Changes requested"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("refund_required", "Refund required"),
                    ("refunded", "Refunded"),
                    ("cancelled", "Cancelled"),
                    ("expired", "Expired"),
                ],
                db_index=True,
                default="draft",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="sponsorauditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("application_created", "Application created"),
                    ("checkout_created", "Checkout created"),
                    ("checkout_failed", "Checkout failed"),
                    ("checkout_cancelled", "Checkout cancelled"),
                    ("checkout_expired", "Checkout expired"),
                    ("payment_confirmed", "Payment confirmed"),
                    ("payment_failed", "Payment failed"),
                    ("changes_requested", "Changes requested"),
                    ("ready_for_review", "Ready for review"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("refund_required", "Refund required"),
                    ("refund_completed", "Refund completed"),
                    ("unpublished", "Unpublished"),
                    ("expired", "Expired"),
                ],
                db_index=True,
                max_length=64,
            ),
        ),
    ]
