from django.db import migrations, models


def classify_central_product(apps, schema_editor):
    SponsorCell = apps.get_model("sponsors", "SponsorCell")
    SponsorApplication = apps.get_model("sponsors", "SponsorApplication")
    SponsorCell.objects.filter(ring=0).update(product_type="central_monthly")
    SponsorApplication.objects.filter(cell__ring=0).update(product_type="central_monthly", term_days=30)


class Migration(migrations.Migration):
    dependencies = [("sponsors", "0006_logo_rotation")]

    operations = [
        migrations.AddField(
            model_name="sponsorcell",
            name="product_type",
            field=models.CharField(choices=[("annual_ring", "Annual Ring Sponsorship"), ("central_monthly", "Central Sponsor of the Month")], db_index=True, default="annual_ring", max_length=32),
        ),
        migrations.AddField(
            model_name="sponsorapplication",
            name="product_type",
            field=models.CharField(choices=[("annual_ring", "Annual Ring Sponsorship"), ("central_monthly", "Central Sponsor of the Month")], db_index=True, default="annual_ring", max_length=32),
        ),
        migrations.AddField(model_name="sponsorapplication", name="term_days", field=models.PositiveIntegerField(default=365)),
        migrations.AlterField(
            model_name="sponsorapplication",
            name="terms_version",
            field=models.CharField(default="2026-06-05-central-monthly-v2", max_length=80),
        ),
        migrations.RunPython(classify_central_product, migrations.RunPython.noop),
    ]
