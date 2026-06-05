"""
Management command: create_sponsor_cells

Creates the 101 sponsor puzzle cells (1 centre + 100 sellable) if they do
not already exist.  Safe to re-run; existing cells are not touched.

Usage:
    python manage.py create_sponsor_cells
"""

from django.core.management.base import BaseCommand

from sponsors.models import SponsorCell

# ring -> number of cells in that ring (outer first)
RING_LAYOUT = [
    (6, 60),  # outer ring   €25/mo each
    (5, 50),  # ring 5       €50/mo each
    (4, 40),  # ring 4       €100/mo each
    (3, 30),  # ring 3       €200/mo each
    (2, 20),  # ring 2       €400/mo each
    (1, 10),  # inner ring   €800/mo each
]


class Command(BaseCommand):
    help = "Populate the 101 sponsor puzzle cells (1 centre + 100 sellable)."

    def handle(self, *args, **options):
        created = 0
        skipped = 0

        # Centre cell
        _, was_created = SponsorCell.objects.get_or_create(
            cell_number=0,
            defaults={"ring": 0, "position_in_ring": 0, "product_type": SponsorCell.ProductType.CENTRAL_MONTHLY},
        )
        if was_created:
            created += 1
            self.stdout.write("  Created centre cell (cell #0)")
        else:
            skipped += 1

        # Sellable cells, numbered 1..100
        cell_number = 1
        for ring, count in RING_LAYOUT:
            for pos in range(count):
                _, was_created = SponsorCell.objects.get_or_create(
                    cell_number=cell_number,
                    defaults={"ring": ring, "position_in_ring": pos},
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1
                cell_number += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created}  |  Already existed: {skipped}"
            )
        )
