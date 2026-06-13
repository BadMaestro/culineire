from django.db import migrations
from decimal import Decimal


PACKAGES = [
    {"name": "Starter",   "tokens": 100,  "price_eur": Decimal("10.00"), "sort_order": 1},
    {"name": "Chef",      "tokens": 300,  "price_eur": Decimal("25.00"), "sort_order": 2},
    {"name": "Sous Chef", "tokens": 600,  "price_eur": Decimal("45.00"), "sort_order": 3},
    {"name": "Head Chef", "tokens": 1000, "price_eur": Decimal("65.00"), "sort_order": 4},
    {"name": "Executive", "tokens": 1400, "price_eur": Decimal("80.00"), "sort_order": 5},
]


def seed_packages(apps, schema_editor):
    TokenPackage = apps.get_model("chef_battle", "TokenPackage")
    for p in PACKAGES:
        TokenPackage.objects.get_or_create(name=p["name"], defaults=p)


def unseed_packages(apps, schema_editor):
    TokenPackage = apps.get_model("chef_battle", "TokenPackage")
    names = [p["name"] for p in PACKAGES]
    TokenPackage.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0013_chefartifact_source_alter_battleevent_event_type"),
    ]

    operations = [
        migrations.RunPython(seed_packages, reverse_code=unseed_packages),
    ]
