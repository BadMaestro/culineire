"""Delete the 421 artifacts handed to two test accounts in July.

`ChefArtifact.source` defaults to `purchased` and the 2026-07-15 seed never
set it, so 421 rows claimed to have been bought when nobody had paid for
anything. Now that buying an artifact actually works (v2.5.1385), a real
purchase and "nobody filled this field in" are the same row, and the ledger
cannot tell them apart.

The Owner's ruling: they were granted to chefs for a test, nobody bought
them, delete them.

WHAT IS DELETED, and the scope is the whole point. Every one of the 421 rows
belongs to `CrestedTen` (210) and `Jam O'Liver` (211) - the Owner's own test
accounts - and all of them were written inside 1.3 seconds on 2026-07-15.
`greenbear` owns none of them, and this migration cannot reach that account
whatever it does.

The filter is deliberately NOT `source="purchased"` alone. A genuine purchase
also carries that value, so a migration written that way would read as "delete
every artifact anyone ever bought" to whoever finds it later. The date bound
says what is actually meant: artifacts that predate the existence of the shop
that could have sold them.

Not reversible. The rows carry no payment, no history and no consequence -
the six `admin_grant` rows and two `drop` rows, which do mean something, are
untouched.
"""
import datetime

from django.db import migrations

# The artifact shop shipped on 2026-08-28. Nothing before it was bought,
# because before it there was nothing to buy with.
SHOP_OPENED = datetime.datetime(2026, 8, 1, tzinfo=datetime.timezone.utc)


def drop_the_test_grants(apps, schema_editor):
    ChefArtifact = apps.get_model("chef_battle", "ChefArtifact")
    ChefArtifact.objects.filter(
        source="purchased", earned_at__lt=SHOP_OPENED,
    ).delete()


def cannot_be_undone(apps, schema_editor):
    """Deliberately a no-op rather than an error.

    Reversing the migration must not fail the whole rollback of a release for
    rows that were test data, but nothing can put them back either."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("chef_battle", "0116_house_stream_is_the_food_trailer"),
    ]

    operations = [
        migrations.RunPython(drop_the_test_grants, cannot_be_undone),
    ]
