from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sponsors", "0003_sponsorroadmapitem_alter_sponsorcell_status_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sponsorapplication",
            name="website_url",
            field=models.URLField(blank=True),
        ),
    ]
