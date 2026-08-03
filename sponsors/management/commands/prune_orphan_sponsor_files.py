"""Delete sponsor upload files that no database row points at.

Written 2026-08-03. An audit on 2026-07-28 counted 603 files under
sponsors/applications/ that nothing references — mostly repeated re-uploads of
the same logo, 35 MB of them. Deleting files on a live server is the one job
where a clever one-liner is worst, so this follows the rule in AGENTS.md 17.10
literally: count first, show examples, list what survives, and only then delete.

Referenced means referenced by ANY of the fields that can hold an upload, on
either model — including the legacy pending-logo field, which is exactly the
kind of column a substring-matching cleanup forgets and then deletes live data
over. A file is only ever a candidate if no field on any row names it.

Nothing is removed without --apply, and even then only inside the one directory
named below: this command cannot be pointed somewhere else.
"""

import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand, CommandError

from sponsors.models import SponsorApplication, SponsorCell

# The only directory this command will ever touch.
TARGET_DIR = "sponsors/applications"

# Every field that can hold a path into that directory. Named explicitly rather
# than discovered, so adding an upload field to either model shows up here as a
# review question instead of silently turning live files into orphans.
FILE_FIELDS = (
    (SponsorCell, ("sponsor_logo", "logo_pending")),
    (SponsorApplication, ("logo",)),
)


class Command(BaseCommand):
    help = "Delete files under sponsors/applications/ that no database row references."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually delete. Without this the command only reports.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Delete at most this many files this run. 0 means no limit.",
        )
        parser.add_argument(
            "--examples",
            type=int,
            default=10,
            help="How many example paths to print (AGENTS.md 17.10 asks for ten).",
        )

    def handle(self, *args, **options):
        # Built here rather than imported once at module load: default_storage
        # caches its location, so a command that took it would ignore a
        # redirected MEDIA_ROOT and reach the real disk anyway. That is not
        # hypothetical — the first run of this command's tests read the
        # developer's live media directory instead of its own fixtures.
        storage = FileSystemStorage(location=settings.MEDIA_ROOT)

        referenced = set()
        for model, fields in FILE_FIELDS:
            for field in fields:
                for value in model.objects.exclude(**{field: ""}).values_list(field, flat=True):
                    if value:
                        referenced.add(str(value).lstrip("/"))

        try:
            _dirs, names = storage.listdir(TARGET_DIR)
        except FileNotFoundError as exc:
            raise CommandError(f"{TARGET_DIR} does not exist in storage.") from exc

        on_disk = [f"{TARGET_DIR}/{name}" for name in sorted(names)]
        orphans = [path for path in on_disk if path not in referenced]
        keepers = [path for path in on_disk if path in referenced]

        total_bytes = 0
        for path in orphans:
            try:
                total_bytes += storage.size(path)
            except (OSError, NotImplementedError):
                pass

        self.stdout.write(f"on_disk={len(on_disk)}")
        self.stdout.write(f"referenced_by_a_row={len(keepers)}")
        self.stdout.write(f"orphans={len(orphans)} bytes={total_bytes} mb={total_bytes / 1048576:.1f}")

        self.stdout.write("SURVIVORS (referenced, never touched):")
        for path in keepers:
            self.stdout.write(f"  KEEP {path}")

        limit = options["examples"]
        self.stdout.write(f"ORPHAN EXAMPLES (first {limit}):")
        for path in orphans[:limit]:
            self.stdout.write(f"  ORPHAN {path}")

        if not orphans:
            self.stdout.write("nothing to delete")
            return

        if not options["apply"]:
            self.stdout.write(
                f"DRY RUN — would delete {len(orphans)} files, {total_bytes / 1048576:.1f} MB. "
                "Re-run with --apply."
            )
            return

        batch = orphans[: options["limit"]] if options["limit"] else orphans
        deleted = 0
        failed = []
        for path in batch:
            # Belt and braces: never delete outside the target directory, whatever
            # storage hands back.
            if os.path.dirname(path).replace("\\", "/") != TARGET_DIR:
                failed.append((path, "outside target directory"))
                continue
            try:
                storage.delete(path)
                deleted += 1
            except OSError as exc:
                failed.append((path, str(exc)))

        self.stdout.write(f"APPLIED deleted={deleted} failed={len(failed)}")
        for path, reason in failed[:10]:
            self.stdout.write(f"  FAILED {path}: {reason}")

        _dirs, after = storage.listdir(TARGET_DIR)
        self.stdout.write(f"on_disk_after={len(after)} (was {len(on_disk)})")
