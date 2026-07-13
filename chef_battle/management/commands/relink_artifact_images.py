"""Re-link Artifact.image fields to image files already on disk, by PK.

Recovery + guard for a known footgun: running
`loaddata chef_battle/fixtures/battle_artifacts.json` overwrites each artifact
row by PK, and because that fixture omits the `image` field, loaddata resets
Artifact.image to its default ("") — blanking every artifact image while the
generated files stay on disk (orphaned). This command re-points blank-image
artifacts at their existing files (named "<slug>-<pk>.png", optionally with a
Django dedup "_suffix"), matched by the trailing PK. It never deletes or
regenerates anything and is safe to re-run (idempotent).

Run it immediately after any loaddata of the artifacts fixture.
"""
import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand

from chef_battle.models import Artifact

_REL_DIR = "chef_battle/artifacts"
_PK_RE = re.compile(r"-(\d+)(?:_[A-Za-z0-9]+)?\.png$")


def _pick(files):
    """Prefer the canonical '<slug>-<pk>.png' over a deduped '..._suffix.png'."""
    canonical = [f for f in files if re.search(r"-\d+\.png$", f)]
    return sorted(canonical or files)[0]


class Command(BaseCommand):
    help = "Re-link blank Artifact.image fields to existing files on disk (by PK)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be re-linked without saving.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        art_dir = os.path.join(str(settings.MEDIA_ROOT), *_REL_DIR.split("/"))
        if not os.path.isdir(art_dir):
            self.stdout.write(self.style.WARNING(f"No artifact media dir: {art_dir}"))
            return

        by_pk: dict[int, list[str]] = {}
        for f in os.listdir(art_dir):
            m = _PK_RE.search(f)
            if m:
                by_pk.setdefault(int(m.group(1)), []).append(f)

        relinked = skipped = 0
        for a in Artifact.objects.filter(image=""):
            files = by_pk.get(a.pk)
            if not files:
                skipped += 1
                continue
            rel = f"{_REL_DIR}/{_pick(files)}"
            if dry:
                self.stdout.write(f"[dry-run] #{a.pk} {a.name} -> {rel}")
            else:
                a.image = rel
                a.save(update_fields=["image"])
                self.stdout.write(f"#{a.pk} {a.name} -> {rel}")
            relinked += 1

        self.stdout.write(self.style.SUCCESS(
            f"relink_artifact_images: {relinked} re-linked, {skipped} still without a file"
            + (" (dry-run)" if dry else "")
        ))
