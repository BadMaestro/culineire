from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("newsfeed", "0009_add_telegram_cta_to_launch_news"),
    ]

    operations = [
        migrations.AddField(
            model_name="newsfeedentry",
            name="image_url",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
