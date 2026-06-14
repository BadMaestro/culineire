from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0025_greenbear_infinite_balance"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appreciationgift",
            name="gift_type",
            field=models.CharField(
                choices=[
                    ("coffee", "Coffee"),
                    ("virtual_beer_toast", "Virtual Beer Toast"),
                    ("virtual_whiskey_toast", "Virtual Whiskey Toast"),
                    ("flowers", "Flowers"),
                    ("celebration_cocktail", "Celebration Cocktail"),
                    ("virtual_champagne_bottle", "Virtual Champagne Bottle"),
                ],
                max_length=32,
            ),
        ),
    ]
