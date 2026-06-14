from decimal import Decimal

from django.db import migrations


def upsert_token_packages(apps, schema_editor):
    from chef_battle.token_config import TOKEN_PACKAGES, cents_to_eur

    TokenPackage = apps.get_model("chef_battle", "TokenPackage")
    canonical_keys = set()

    for spec in TOKEN_PACKAGES:
        final_price = cents_to_eur(spec["final_price_cents"])
        canonical_keys.add(spec["key"])

        # Try to find existing package by name first (handles legacy-keyed rows),
        # then by key (handles clean runs and idempotent replays).
        pkg = (
            TokenPackage.objects.filter(name=spec["name"]).first()
            or TokenPackage.objects.filter(key=spec["key"]).first()
        )
        if pkg:
            pkg.key = spec["key"]
            pkg.name = spec["name"]
            pkg.tokens = spec["tokens"]
            pkg.price_eur = final_price
            pkg.discount_percent = spec["discount_percent"]
            pkg.is_active = True
            pkg.sort_order = spec["sort_order"]
            pkg.save(update_fields=["key", "name", "tokens", "price_eur", "discount_percent", "is_active", "sort_order"])
        else:
            TokenPackage.objects.create(
                key=spec["key"],
                name=spec["name"],
                tokens=spec["tokens"],
                price_eur=final_price,
                discount_percent=spec["discount_percent"],
                is_active=True,
                sort_order=spec["sort_order"],
            )

    # Deactivate any packages not in the canonical config
    TokenPackage.objects.exclude(key__in=canonical_keys).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0022_token_package_key_discount"),
    ]

    operations = [
        migrations.RunPython(upsert_token_packages, migrations.RunPython.noop),
    ]
