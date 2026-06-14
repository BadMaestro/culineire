from decimal import Decimal

from django.db import migrations


def upsert_token_packages(apps, schema_editor):
    from chef_battle.token_config import TOKEN_PACKAGES, cents_to_eur

    TokenPackage = apps.get_model("chef_battle", "TokenPackage")
    for spec in TOKEN_PACKAGES:
        TokenPackage.objects.update_or_create(
            key=spec["key"],
            defaults={
                "name": spec["name"],
                "tokens": spec["tokens"],
                "price_eur": cents_to_eur(spec["final_price_cents"]),
                "discount_percent": spec["discount_percent"],
                "is_active": True,
                "sort_order": spec["sort_order"],
            },
        )
    # Deactivate any packages not in the canonical config
    canonical_keys = {spec["key"] for spec in TOKEN_PACKAGES}
    TokenPackage.objects.exclude(key__in=canonical_keys).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0022_token_package_key_discount"),
    ]

    operations = [
        migrations.RunPython(upsert_token_packages, migrations.RunPython.noop),
    ]
