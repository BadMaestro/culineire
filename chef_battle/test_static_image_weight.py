"""W3 / W3-FIX — never again: template {% static %} AND CSS url() image weight.

Bolt #3121 + #3126 / Owner: NEVER AGAIN ALLOW OVERLOADS OF THE ARENA.

The Arena incident was a CSS url() to a 2.6 MB floor-plate — invisible to a
templates-only scan. This guard walks:

1. templates/**/*.{html,txt,htm} for {% static '...' %}
2. static/css/**/*.css for url(...) image refs (strip leading /static/)

Caps (first matching prefix wins):

- images/chef_battle/widget/: 100 KB — sidebar icons (W1 target ~8 KB)
- images/crowd/: 50 KB
- img/arena/: 50 KB
- images/chef_battle/arena/: 100 KB — decorative plates
- images/hero*, my-hero*, *avatar*: 800 KB — HONEST bite below observed ~2.5 MB
  heroes. Suite stays red until Owner rules on hero art (Bolt #3126).
- images/logo*: 400 KB
- default: 150 KB

Must FAIL when floor-plate is wired (ee88e451~1) and remain honest on main.
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
CSS_URL = re.compile(
    r"""url\(\s*['"]?([^'")\s]+)['"]?\s*\)""",
    re.IGNORECASE,
)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif"}

CAPS: list[tuple[str, int, str]] = [
    ("images/chef_battle/widget/", 100_000, "sidebar icons — must be WebP ~8KB after W1"),
    ("images/crowd/", 50_000, "crowd face assets"),
    ("img/arena/", 50_000, "arena atmosphere textures"),
    ("images/chef_battle/arena/", 100_000, "arena decorative plates"),
    ("images/hero", 800_000, "hero art — honest bite; red until Owner rules (#3126)"),
    ("images/my-hero", 800_000, "authoring heroes — honest bite"),
    ("images/logo", 400_000, "brand marks"),
    ("images/male-avatar", 800_000, "default avatar — honest bite"),
    ("images/neutral-avatar", 800_000, "default avatar — honest bite"),
    ("images/female-avatar", 800_000, "default avatar — honest bite"),
    ("", 150_000, "default UI chrome (Bolt opening cap)"),
]


def _cap_for(rel: str) -> tuple[int, str]:
    norm = rel.replace("\\", "/").lstrip("/")
    for prefix, cap, reason in CAPS:
        if not prefix or norm.startswith(prefix):
            return cap, reason
    return 150_000, "default"


def _is_image_rel(rel: str) -> bool:
    return Path(rel.split("?", 1)[0]).suffix.lower() in IMAGE_SUFFIXES


def _normalize_ref(raw: str) -> str | None:
    rel = raw.strip().split("?", 1)[0].strip()
    if not rel or rel.startswith("data:") or "://" in rel:
        return None
    if rel.startswith("/static/"):
        rel = rel[len("/static/") :]
    rel = rel.lstrip("/")
    if not _is_image_rel(rel):
        return None
    return rel.replace("\\", "/")


def _collect_template_refs(templates_root: Path) -> set[str]:
    refs: set[str] = set()
    for path in templates_root.rglob("*"):
        if path.suffix not in {".html", ".txt", ".htm"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in STATIC_TAG.finditer(text):
            rel = _normalize_ref(match.group(1))
            if rel:
                refs.add(rel)
    return refs


def _collect_css_refs(css_root: Path) -> set[str]:
    refs: set[str] = set()
    if not css_root.is_dir():
        return refs
    for path in css_root.rglob("*.css"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in CSS_URL.finditer(text):
            rel = _normalize_ref(match.group(1))
            if rel:
                refs.add(rel)
    return refs


def collect_all_refs(root: Path) -> set[str]:
    return _collect_template_refs(root / "templates") | _collect_css_refs(root / "static" / "css")


class ReferencedStaticImageWeightTests(SimpleTestCase):
    """Fail if any template/CSS-referenced static image exceeds its byte cap."""

    def test_referenced_static_images_under_byte_caps(self):
        root = Path(settings.BASE_DIR)
        static_root = root / "static"
        self.assertTrue((root / "templates").is_dir())
        self.assertTrue(static_root.is_dir())

        refs = collect_all_refs(root)
        self.assertTrue(refs, "no template/CSS image refs found — test is not scanning")

        # CSS scan must be live (W3-FIX-1): prove we are not templates-only.
        css_refs = _collect_css_refs(root / "static" / "css")
        self.assertTrue(css_refs, "CSS url() scan found nothing — guard is blind again")

        offenders: list[str] = []
        for rel in sorted(refs):
            path = static_root / rel
            if not path.is_file():
                continue
            size = path.stat().st_size
            cap, reason = _cap_for(rel)
            if size > cap:
                offenders.append(f"{rel}: {size} B > cap {cap} B ({reason})")

        if offenders:
            self.fail(
                "Referenced static image(s) exceed byte cap(s). "
                "Disconnect or shrink before merge.\n"
                + "\n".join(offenders)
            )
