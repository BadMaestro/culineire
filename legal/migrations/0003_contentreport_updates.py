from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("legal", "0002_contentreport_reporter_user_linked_message"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentreport",
            name="organisation",
            field=models.CharField(
                blank=True,
                max_length=200,
                verbose_name="Organisation (optional)",
            ),
        ),
        migrations.AddField(
            model_name="contentreport",
            name="evidence_url",
            field=models.CharField(
                blank=True,
                max_length=500,
                verbose_name="Link to original source or evidence (optional)",
            ),
        ),
        migrations.AddField(
            model_name="contentreport",
            name="good_faith_confirmed",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "I confirm this report is made in good faith and the information "
                    "is accurate to the best of my knowledge."
                ),
                verbose_name="Good faith declaration",
            ),
        ),
        migrations.AddField(
            model_name="contentreport",
            name="status",
            field=models.CharField(
                choices=[
                    ("open", "Open"),
                    ("under_review", "Under review"),
                    ("resolved", "Resolved"),
                    ("dismissed", "Dismissed"),
                ],
                default="open",
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AddField(
            model_name="contentreport",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="contentreport",
            name="handled_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Handled at"
            ),
        ),
        migrations.AddField(
            model_name="contentreport",
            name="internal_notes",
            field=models.TextField(blank=True, verbose_name="Internal notes"),
        ),
        migrations.AlterField(
            model_name="contentreport",
            name="report_type",
            field=models.CharField(
                choices=[
                    ("copyright", "Copyright infringement"),
                    ("watermark", "Watermarked or unlicensed image"),
                    ("inaccurate_credit", "Inaccurate or missing credit"),
                    ("stolen_recipe", "Stolen or uncredited recipe"),
                    ("privacy_data", "Privacy or personal data concern"),
                    ("impersonation", "Impersonation or fake identity"),
                    ("defamation", "Defamatory or harmful content"),
                    ("food_safety", "Food safety or allergen concern"),
                    ("spam", "Spam or promotional abuse"),
                    ("other", "Other"),
                ],
                default="copyright",
                max_length=30,
                verbose_name="Type of issue",
            ),
        ),
    ]
