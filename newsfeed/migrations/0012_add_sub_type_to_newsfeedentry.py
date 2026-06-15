from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('newsfeed', '0011_alter_newsfeedentry_entry_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='newsfeedentry',
            name='sub_type',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
