"""Set the tagline on one sponsor cell.

Written 2026-08-03 because the alternative was an ad-hoc `manage.py shell -c`
against production, and a one-off shell leaves nothing behind: no record of what
ran, no dry run, no second chance to read the change before it lands. A named
command is in the repository, is reviewable, prints what it is about to do, and
does nothing at all until it is told to apply.

It edits exactly one field, `sponsor_tagline`, which is the line the arena's
sponsor card shows under the sponsor's name. It cannot change status, price,
ownership or anything else a sponsor has paid for.
"""

from django.core.management.base import BaseCommand, CommandError

from sponsors.models import SponsorCell


class Command(BaseCommand):
    help = "Set sponsor_tagline on one sponsor cell, matched by name or cell number."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            help="Case-insensitive substring of sponsor_name. Must match exactly one cell.",
        )
        parser.add_argument(
            "--cell-number",
            type=int,
            help="Exact cell number. Use when a name matches more than one cell.",
        )
        parser.add_argument("--tagline", required=True, help="The new tagline text.")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write it. Without this the command only reports.",
        )

    def handle(self, *args, **options):
        name = options.get("name")
        cell_number = options.get("cell_number")
        tagline = options["tagline"]

        if not name and cell_number is None:
            raise CommandError("Give --name or --cell-number.")

        rows = SponsorCell.objects.all()
        if cell_number is not None:
            rows = rows.filter(cell_number=cell_number)
        if name:
            rows = rows.filter(sponsor_name__icontains=name)
        rows = rows.order_by("cell_number")

        matched = list(rows)
        self.stdout.write(f"matched={len(matched)}")
        for cell in matched:
            self.stdout.write(
                f"  cell={cell.cell_number} pk={cell.pk} status={cell.status} "
                f"name={cell.sponsor_name!r} tagline={cell.sponsor_tagline!r}"
            )

        if not matched:
            raise CommandError("Nothing matched — refusing to guess.")
        if len(matched) > 1:
            # Never write to a set the caller did not mean to name. Narrowing is
            # cheap; a tagline on the wrong customer's box is not.
            raise CommandError(
                f"{len(matched)} cells matched. Narrow it with --cell-number."
            )

        cell = matched[0]
        if cell.sponsor_tagline == tagline:
            self.stdout.write("unchanged — the cell already carries this tagline")
            return

        if not options["apply"]:
            self.stdout.write(
                f"DRY RUN — would set cell={cell.cell_number} tagline "
                f"{cell.sponsor_tagline!r} -> {tagline!r}. Re-run with --apply."
            )
            return

        before = cell.sponsor_tagline
        SponsorCell.objects.filter(pk=cell.pk).update(sponsor_tagline=tagline)
        after = SponsorCell.objects.get(pk=cell.pk).sponsor_tagline
        self.stdout.write(
            f"APPLIED cell={cell.cell_number} {before!r} -> {after!r}"
        )
        if after != tagline:
            raise CommandError("Write did not stick — read back a different value.")
