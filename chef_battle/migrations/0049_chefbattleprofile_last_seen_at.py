from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0048_add_is_executive_set_greenbear"),
    ]

    operations = [
        migrations.AddField(
            model_name="chefbattleprofile",
            name="last_seen_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
