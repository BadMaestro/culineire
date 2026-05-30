from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sponsors", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sponsorcell",
            name="enquiry_company",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="sponsorcell",
            name="enquiry_email",
            field=models.EmailField(blank=True),
        ),
        migrations.AddField(
            model_name="sponsorcell",
            name="enquiry_message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="sponsorcell",
            name="enquiry_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="sponsorcell",
            name="enquiry_submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sponsorcell",
            name="enquiry_website",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="sponsorcell",
            name="logo_offset_x",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="sponsorcell",
            name="logo_offset_y",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="sponsorcell",
            name="logo_pending",
            field=models.ImageField(
                blank=True, null=True, upload_to="sponsors/pending/"
            ),
        ),
        migrations.AddField(
            model_name="sponsorcell",
            name="logo_scale",
            field=models.FloatField(default=1.0),
        ),
    ]
