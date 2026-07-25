"""W3 — never again: referenced static images must stay under byte caps.

Bolt #3121 / Owner: NEVER AGAIN ALLOW OVERLOADS OF THE ARENA.

Walks every template for `{% static '...' %}` image refs and fails when a
referenced file on disk exceeds its directory cap. Cap rationale:

- images/chef_battle/widget/: 100 KB — sidebar icons (Bolt target ~8 KB each
  after W1; 100 KB catches today's ~122–188 KB PNGs before the shrink).
- images/crowd/: 50 KB — atmospheric face webps (~4 KB today).
- img/arena/: 50 KB — atmosphere textures (must stay tiny / disconnected).
- default: 150 KB — Bolt's suggested opening cap for general UI chrome.
- heroes / recipe / article uploads under media/ are NOT scanned (not
  `{% static %}`); static hero plates under images/ that are real photos may
  need a later per-path exception with Bolt approval.

Must FAIL on the pre-W1 tree (widget PNGs) and PASS after W1 retargets WebP.
"""
from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

STATIC_TAG = re.compile(
    r"""\{%\s*static\s+['"]([^'"]+)['"]\s*%\}""",
    re.IGNORECASE,
)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif"}

# Bytes. First matching prefix wins.
# Hero/full-bleed photos are Owner-locked page art — not sidebar chrome.
# Widget icons are the overload that amputated the Arena UX (Bolt #3121).
CAPS: list[tuple[str, int, str]] = [
    ("images/chef_battle/widget/", 100_000, "sidebar icons — must be WebP ~8KB after W1"),
    ("images/crowd/", 50_000, "crowd face assets"),
    ("img/arena/", 50_000, "arena atmosphere textures"),
    ("images/chef_battle/arena/", 100_000, "arena decorative plates (prefer disconnect over MB PNGs)"),
    ("images/hero", 3_000_000, "full-bleed page heroes (Owner-locked art)"),
    ("images/my-hero", 3_000_000, "authoring heroes"),
    ("images/logo", 400_000, "brand marks"),
    ("images/male-avatar", 3_000_000, "default avatar plate"),
    ("images/neutral-avatar", 3_000_000, "default avatar plate"),
    ("images/female-avatar", 3_000_000, "default avatar plate"),
    ("", 150_000, "default UI chrome (Bolt opening cap)"),
]


def _cap_for(rel: str) -> tuple[int, str]:
    norm = rel.replace("\\", "/").lstrip("/")
    for prefix, cap, reason in CAPS:
        if not prefix or norm.startswith(prefix):
            return cap, reason
    return 150_000, "default"


def _collect_static_image_refs(templates_root: Path) -> set[str]:
    refs: set[str] = set()
    for path in templates_root.rglob("*"):
        if path.suffix not in {".html", ".txt", ".htm"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in STATIC_TAG.finditer(text):
            rel = match.group(1).split("?", 1)[0].lstrip("/")
            if Path(rel).suffix.lower() in IMAGE_SUFFIXES:
                refs.add(rel)
    return refs


class ReferencedStaticImageWeightTests(SimpleTestCase):
    """Fail the suite if any template-referenced static image exceeds its cap."""

    def test_referenced_static_images_under_byte_caps(self):
        root = Path(settings.BASE_DIR)
        templates_root = root / "templates"
        static_root = root / "static"
        self.assertTrue(templates_root.is_dir(), f"missing templates at {templates_root}")
        self.assertTrue(static_root.is_dir(), f"missing static at {static_root}")

        refs = _collect_static_image_refs(templates_root)
        self.assertTrue(refs, "no {% static %} image refs found — test is not scanning")

        offenders: list[str] = []
        missing: list[str] = []
        for rel in sorted(refs):
            path = static_root / rel
            if not path.is_file():
                # Manifest / optional assets: skip missing rather than false-fail.
                missing.append(rel)
                continue
            size = path.stat().st_size
            cap, reason = _cap_for(rel)
            if size > cap:
                offenders.append(
                    f"{rel}: {size} B > cap {cap} B ({reason})"
                )

        if offenders:
            self.fail(
                "Referenced static image(s) exceed byte cap(s). "
                "Disconnect or shrink before merge.\n"
                + "\n".join(offenders)
            )
