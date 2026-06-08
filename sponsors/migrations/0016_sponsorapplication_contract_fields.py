from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sponsors", "0015_weekly_ring_product_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="sponsorapplication",
            name="contract_reference",
            field=models.CharField(blank=True, db_index=True, max_length=30),
        ),
        migrations.AddField(
            model_name="sponsorapplication",
            name="contract_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sponsorapplication",
            name="contract_email_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", "Pending"),
                    ("sent", "Sent"),
                    ("failed", "Failed"),
                    ("resent", "Resent"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="sponsorauditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("application_created", "Application created"),
                    ("checkout_created", "Checkout created"),
                    ("checkout_created_after_declaration", "Checkout created after declaration"),
                    ("checkout_failed", "Checkout failed"),
                    ("checkout_cancelled", "Checkout cancelled"),
                    ("checkout_expired", "Checkout expired"),
                    ("payment_confirmed", "Payment confirmed"),
                    ("applicant_declaration_accepted", "Applicant declaration accepted"),
                    ("payment_received_pending_compliance_review", "Payment received pending compliance review"),
                    ("manual_compliance_clear", "Manual compliance clear"),
                    ("payment_failed", "Payment failed"),
                    ("changes_requested", "Changes requested"),
                    ("ready_for_review", "Ready for review"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("refund_required", "Refund required"),
                    ("refund_completed", "Refund completed"),
                    ("unpublished", "Unpublished"),
                    ("expired", "Expired"),
                    ("compliance_blocked", "Compliance blocked"),
                    ("sanctions_screening_completed", "Sanctions screening completed"),
                    ("sanctions_possible_match_created", "Sanctions possible match created"),
                    ("sanctions_match_false_positive", "Sanctions match marked false positive"),
                    ("sanctions_match_manually_cleared", "Sanctions match manually cleared"),
                    ("sanctions_match_blocked", "Sanctions match blocked"),
                    ("approval_blocked_sanctions", "Approval blocked by sanctions review"),
                    ("contract_sent", "Contract email sent"),
                    ("contract_email_failed", "Contract email failed"),
                    ("contract_email_resent", "Contract email resent"),
                ],
                db_index=True,
                max_length=64,
            ),
        ),
    ]
