"""The fourth surface: uploaded media.

`chef_battle/test_static_image_weight.py` watches three surfaces — templates,
CSS `url()` and Python string maps — and all three only ever look inside
`static/`. Uploaded photographs live in `media/`, so nothing was watching the
heaviest thing this site serves.

What that cost, measured on production 2026-07-26 in a real browser:

    a public recipe page          4,198 KB of images, 3,951 KB of it media
    one gallery PNG               2,291 KB, rendered at 473x378
    author avatars                1.6-2.4 MB each, rendered at 38x38
    files over 300 KB in media    1,224, the largest 3.2 MB

The fix was `generate_media_webp`, which writes a `.webp` sibling beside each
source, plus `webp_url()` so templates serve the sibling when it exists.

This test does not police what people upload — an editor must be free to upload
a 12 MP photograph. It polices the thing that actually reaches a visitor: if a
heavy uploaded image is being SERVED without a lighter sibling next to it, the
conversion has not been run and somebody should run it.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg"}

# An uploaded photograph above this size, with no WebP sibling, is weight a
# visitor pays for. Chosen from the measurement above: everything that hurt was
# far above it, and ordinary small uploads sit far below.
HEAVY_BYTES = 300_000

# How many offenders to name before the failure message stops being readable.
REPORT_LIMIT = 15


class UploadedMediaHasLighterSiblingTests(SimpleTestCase):
    """Fail when heavy uploaded images are served with no WebP sibling."""

    def test_media_root_is_reachable(self):
        """A guard that silently scans nothing is worse than no guard.

        If MEDIA_ROOT moves or is empty in a given environment, say so plainly
        rather than passing on an empty directory.
        """
        root = Path(settings.MEDIA_ROOT)
        if not root.is_dir():
            self.skipTest(f"MEDIA_ROOT is not a directory here: {root}")
        self.assertTrue(
            any(root.rglob("*")),
            f"MEDIA_ROOT is empty: {root} — the media scan is testing nothing",
        )

    def test_heavy_uploads_have_a_webp_sibling(self):
        root = Path(settings.MEDIA_ROOT)
        if not root.is_dir():
            self.skipTest(f"MEDIA_ROOT is not a directory here: {root}")

        offenders: list[tuple[int, str]] = []
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            size = path.stat().st_size
            if size <= HEAVY_BYTES:
                continue
            if path.with_suffix(".webp").exists():
                continue
            offenders.append((size, str(path.relative_to(root))))

        if offenders:
            offenders.sort(reverse=True)
            shown = "\n".join(f"  {s:>9,} B  {p}" for s, p in offenders[:REPORT_LIMIT])
            more = ""
            if len(offenders) > REPORT_LIMIT:
                more = f"\n  ... and {len(offenders) - REPORT_LIMIT} more"
            total = sum(s for s, _ in offenders)
            self.fail(
                f"{len(offenders)} uploaded image(s) over {HEAVY_BYTES:,} B are served "
                f"with no WebP sibling, {total:,} B in total.\n"
                f"Run: manage.py generate_media_webp\n"
                f"Originals are never modified — the command only adds siblings.\n"
                f"{shown}{more}"
            )
