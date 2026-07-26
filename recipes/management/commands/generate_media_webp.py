"""Write a WebP sibling beside every uploaded image. Originals are never touched.

Measured on production 2026-07-26: 1,224 files under MEDIA_ROOT exceed 300 KB and
the largest are 3.2 MB. A public recipe page served 4,198 KB of images, 3,951 KB
of it from /media/, for photographs rendered at a few hundred pixels.

This command only ADDS files. It never deletes, never overwrites an original, and
skips any sibling that is already newer than its source, so it is safe to re-run
and safe to interrupt. Templates pick the sibling up through the ``webp`` filter
in ``recipes.templatetags.media_webp``; until a sibling exists the page keeps
serving the original, so a partial run is never a broken page.

    manage.py generate_media_webp --dry-run
    manage.py generate_media_webp --min-bytes 200000
    manage.py generate_media_webp --limit 50
"""
from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg"}


class Command(BaseCommand):
    help = "Generate a .webp sibling for uploaded images. Originals are kept untouched."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would be written and write nothing.")
        parser.add_argument("--min-bytes", type=int, default=100_000,
                            help="Skip sources smaller than this (default 100000).")
        parser.add_argument("--quality", type=int, default=82,
                            help="WebP quality (default 82).")
        parser.add_argument("--limit", type=int, default=0,
                            help="Stop after this many conversions. 0 means no limit.")

    def handle(self, *args, **opts):
        try:
            from PIL import Image
        except ImportError:
            self.stderr.write("Pillow is not installed; nothing done.")
            return

        root = Path(settings.MEDIA_ROOT)
        if not root.is_dir():
            self.stderr.write(f"MEDIA_ROOT does not exist: {root}")
            return

        dry, min_bytes = opts["dry_run"], opts["min_bytes"]
        quality, limit = opts["quality"], opts["limit"]

        written = skipped = failed = 0
        src_bytes = out_bytes = 0

        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            size = path.stat().st_size
            if size < min_bytes:
                continue

            target = path.with_suffix(".webp")
            if target.exists() and target.stat().st_mtime >= path.stat().st_mtime:
                skipped += 1
                continue

            if dry:
                self.stdout.write(f"would write {target.relative_to(root)}  ({size} B source)")
                written += 1
                src_bytes += size
            else:
                try:
                    with Image.open(path) as im:
                        has_alpha = im.mode in ("RGBA", "LA") or (
                            im.mode == "P" and "transparency" in im.info)
                        out = im.convert("RGBA" if has_alpha else "RGB")
                        # Same pixel dimensions on purpose: nothing in any layout
                        # moves, only the bytes on the wire change.
                        tmp = target.with_suffix(".webp.tmp")
                        out.save(tmp, "WEBP", quality=quality, method=6)
                        os.replace(tmp, target)
                except Exception as exc:  # a bad upload must not stop the run
                    failed += 1
                    self.stderr.write(f"FAILED {path.relative_to(root)}: {exc}")
                    continue
                written += 1
                src_bytes += size
                out_bytes += target.stat().st_size

            if limit and written >= limit:
                break

        saved = src_bytes - out_bytes
        pct = (100.0 * saved / src_bytes) if src_bytes else 0.0
        self.stdout.write(
            f"{'DRY RUN: ' if dry else ''}written {written}, already current {skipped}, "
            f"failed {failed}"
        )
        if not dry and written:
            self.stdout.write(
                f"sources {src_bytes} B -> webp {out_bytes} B  (-{pct:.1f}%)"
            )
