"""
Data migration: convert ring 6 cells to WEEKLY_RING with zone-based pricing.

Zone mapping (cell_number → price_override_cents):
  cells 1–8  and 54–60 : 2500  (€25/wk — top zone)
  cells 9–15 and 47–53 : 2000  (€20/wk — upper sides)
  cells 16–23 and 39–46: 1000  (€10/wk — lower sides)
  cells 24–38           :  500  (€5/wk  — bottom zone)

Only product_type and price_override_cents are written; cell status is never touched.
The migration is idempotent: re-running it produces the same result.
"""

from django.db import migrations


def _weekly_price_for_cell(cell_number):
    if (1 <= cell_number <= 8) or (54 <= cell_number <= 60):
        return 2500
    if (9 <= cell_number <= 15) or (47 <= cell_number <= 53):
        return 2000
    if (16 <= cell_number <= 23) or (39 <= cell_number <= 46):
        return 1000
    if 24 <= cell_number <= 38:
        return 500
    return None


def set_ring6_weekly(apps, schema_editor):
    SponsorCell = apps.get_model("sponsors", "SponsorCell")
    for cell in SponsorCell.objects.filter(ring=6):
        price = _weekly_price_for_cell(cell.cell_number)
        if price is not None:
            cell.product_type = "weekly_ring"
            cell.price_override_cents = price
            cell.save(update_fields=["product_type", "price_override_cents"])


def undo_ring6_weekly(apps, schema_editor):
    SponsorCell = apps.get_model("sponsors", "SponsorCell")
    for cell in SponsorCell.objects.filter(ring=6):
        cell.product_type = "annual_ring"
        cell.price_override_cents = None
        cell.save(update_fields=["product_type", "price_override_cents"])


class Migration(migrations.Migration):

    dependencies = [
        ("sponsors", "0013_sponsorcell_price_override_cents"),
    ]

    operations = [
        migrations.RunPython(set_ring6_weekly, undo_ring6_weekly),
    ]
