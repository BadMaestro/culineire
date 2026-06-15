from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0031_compliance_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ChefBattleProfile: payout eligibility flags
        migrations.AddField(
            model_name="chefbattleprofile",
            name="reward_agreement_accepted",
            field=models.BooleanField(
                default=False,
                help_text="Chef has accepted the Chef Reward Agreement",
            ),
        ),
        migrations.AddField(
            model_name="chefbattleprofile",
            name="stripe_connect_onboarded",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Stripe Connect onboarding completed",
            ),
        ),
        # ChefRewardAgreement
        migrations.CreateModel(
            name="ChefRewardAgreement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("accepted_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("agreement_version", models.CharField(default="1.0", max_length=20)),
                ("consent_text_snapshot", models.TextField(help_text="Full agreement text shown to chef at acceptance, frozen for audit")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                (
                    "chef",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reward_agreements",
                        to="recipes.recipeauthor",
                    ),
                ),
            ],
            options={"ordering": ["-accepted_at"]},
        ),
        # DAC7Record
        migrations.CreateModel(
            name="DAC7Record",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("legal_name", models.CharField(max_length=200)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("primary_address", models.TextField(blank=True)),
                ("country_of_tax_residence", models.CharField(help_text="ISO 3166-1 alpha-2 country code", max_length=2)),
                ("tax_identification_number", models.CharField(blank=True, max_length=50)),
                ("business_name", models.CharField(blank=True, max_length=200)),
                ("business_registration_number", models.CharField(blank=True, max_length=100)),
                ("stripe_connect_account_id", models.CharField(blank=True, db_index=True, max_length=100)),
                (
                    "verification_status",
                    models.CharField(
                        choices=[
                            ("unverified", "Unverified"),
                            ("pending", "Pending Verification"),
                            ("verified", "Verified"),
                            ("failed", "Verification Failed"),
                        ],
                        db_index=True,
                        default="unverified",
                        max_length=12,
                    ),
                ),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "chef",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dac7_record",
                        to="recipes.recipeauthor",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # PayoutRequest
        migrations.CreateModel(
            name="PayoutRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount_reward_tokens", models.PositiveIntegerField(help_text="Number of approved reward tokens being redeemed")),
                (
                    "payout_rate_snapshot",
                    models.DecimalField(
                        decimal_places=5,
                        default="0.02500",
                        help_text="EUR per token at request time — locked and immutable after creation",
                        max_digits=8,
                    ),
                ),
                (
                    "gross_payout_eur",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Gross payout before any deductions (tokens × rate)",
                        max_digits=10,
                    ),
                ),
                ("currency", models.CharField(default="eur", max_length=3)),
                ("stripe_connect_account_id", models.CharField(blank=True, db_index=True, max_length=100)),
                ("stripe_transfer_id", models.CharField(blank=True, db_index=True, max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Review"),
                            ("under_review", "Under Review"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("on_hold", "On Hold — Compliance"),
                            ("paid", "Paid Out"),
                            ("reversed", "Reversed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True)),
                ("compliance_flags", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "chef",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payout_requests",
                        to="recipes.recipeauthor",
                    ),
                ),
                (
                    "dac7_record",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payout_requests",
                        to="chef_battle.dac7record",
                    ),
                ),
                (
                    "reward_agreement",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payout_requests",
                        to="chef_battle.chefrewardagreement",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_payout_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-requested_at"]},
        ),
    ]
