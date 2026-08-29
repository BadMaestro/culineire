"""W3 / W3-FIX / W9 — never again: image weight on every surface that can name a file.

Owner, after the Arena fell over: NEVER AGAIN ALLOW OVERLOADS OF THE ARENA.

The history of this guard is the history of surfaces nobody was scanning:

1. v1 scanned templates only. It would NOT have caught the incident it was built
   for: the 2.6 MB floor-plate was a CSS url() in arena_command_deck.css, never a
   {% static %} tag.
2. v2 added static/css/**/*.css. Then 33 MB turned up that neither scan could
   see, because it was named in PYTHON — CATEGORY_IMAGE_MAP in recipes/views.py
   and the default avatar map in recipes/models.py.
3. v3 (this file) adds Python, and separates real payload from <picture>
   fallbacks, which are not downloads and must not be counted as if they were.

The lesson is not "add another regex". When something slips past, ask which
SURFACE was unscanned, not which pattern to widen.

PAYLOAD vs FALLBACK
-------------------
This codebase writes its <picture> blocks on one line:

    <picture><source srcset="...webp" type="image/webp"><img src="...png"></picture>

The WebP in the <source> is what a browser actually fetches. The PNG in the
<img> is a fallback for browsers that have not existed for years. Counting a
fallback as live weight is how "99 MB of live weight" was once reported to the
Owner when the real figure was a fraction of that. Payload is capped and blocks
the suite; fallbacks are held to a sanity ceiling only.
"""
from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

STATIC_TAG = re.compile(r"""\{%\s*static\s+['"]([^'"]+)['"]\s*%\}""", re.IGNORECASE)
CSS_URL = re.compile(r"""url\(\s*['"]?([^'")\s]+)['"]?\s*\)""", re.IGNORECASE)
# Python: static("...") calls and bare quoted paths that end in an image suffix.
PY_REF = re.compile(
    r"""['"]((?:[\w./-]+/)?[\w.-]+\.(?:png|jpg|jpeg|webp|gif|svg|avif))['"]""",
    re.IGNORECASE,
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif"}

# Python files that name images without ever serving them.
PY_SKIP_PARTS = {"migrations", "scratchpad", "node_modules", ".venv", "venv"}
PY_SKIP_NAMES = {"release_journal.py"}  # a prose changelog full of filenames
# Python that builds SOCIAL preview URLs rather than page markup. Named
# explicitly, never pattern-matched: a silent exclusion is how a guard goes blind.
PY_SOCIAL_NAMES = {"telegram_preview.py"}

PAYLOAD, FALLBACK, SOCIAL = "payload", "fallback", "social"

# og:image / twitter:image are absolute URLs handed to a social scraper. They
# are not fetched when a visitor loads the page. Counting them as payload is how
# a hero that is only ever a <picture> fallback still looks like live weight —
# the mistake that produced a badly inflated weight report once already.
SOCIAL_MARKERS = ("og_image", "twitter_image", "og:image", "twitter:image")

CAPS: list[tuple[str, int, str]] = [
    ("images/chef_battle/widget/", 100_000, "sidebar icons — WebP, ~3-5 KB each"),
    ("images/crowd/", 50_000, "crowd face assets"),
    ("img/arena/", 50_000, "arena atmosphere textures"),
    ("images/chef_battle/arena/", 100_000, "arena decorative plates"),
    # Every live hero is now WebP under 220 KB (v2.5.594). 400 KB forbids a
    # regression to PNG without forbidding legitimate art.
    ("images/hero", 400_000, "hero art — live heroes are WebP under 220 KB"),
    ("images/my-hero", 400_000, "authoring heroes — WebP"),
    ("images/categories/", 400_000, "category cards — WebP, referenced from Python"),
    ("images/logo", 400_000, "brand marks"),
    ("images/male-avatar", 400_000, "default avatar — WebP"),
    ("images/neutral-avatar", 400_000, "default avatar — WebP"),
    ("images/female-avatar", 400_000, "default avatar — WebP"),
    # THE OFF-AIR CAMERA CARD, and the only entry here the Owner chose by
    # name. It is his own animated test card: 960x540, 28 frames, 1.3 MB as
    # an animated WebP - the source GIF is 9.7 MB. A still frame was shipped
    # in v2.5.1391 at 86 KB WITHOUT ASKING HIM, which was not mine to decide;
    # he asked for the animation and this cap is his answer to the cost.
    #
    # It is shown only when the camera is OFF and it is lazy-loaded, so it is
    # not on the critical path of any page. If it ever stops being lazy, this
    # entry must go rather than the loading attribute.
    ("images/chef_battle/live_camera_placeholder", 1_500_000,
     "the Owner's animated off-air card, his call, 2026-08-29"),
    ("", 150_000, "default UI chrome"),
]

# A fallback is never fetched by a current browser, so it is not live weight.
# This ceiling exists only to catch something absurd being parked there.
FALLBACK_CEILING = 3_000_000


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


def _add(refs: dict[str, set[str]], rel: str | None, kind: str) -> None:
    if rel:
        refs.setdefault(rel, set()).add(kind)


def _collect_template_refs(templates_root: Path) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    if not templates_root.is_dir():
        return refs
    for path in templates_root.rglob("*"):
        if path.suffix not in {".html", ".txt", ".htm"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            # A one-line <picture> that offers WebP: the <source> is the payload,
            # everything else on that line is the fallback nobody downloads.
            picture_line = "image/webp" in line and "<source" in line
            social_line = any(marker in line for marker in SOCIAL_MARKERS)
            for match in STATIC_TAG.finditer(line):
                rel = _normalize_ref(match.group(1))
                if rel is None:
                    continue
                if social_line:
                    _add(refs, rel, SOCIAL)
                elif picture_line and not rel.endswith((".webp", ".avif")):
                    _add(refs, rel, FALLBACK)
                else:
                    _add(refs, rel, PAYLOAD)
    return refs


def _collect_css_refs(css_root: Path) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    if not css_root.is_dir():
        return refs
    for path in css_root.rglob("*.css"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in CSS_URL.finditer(text):
            _add(refs, _normalize_ref(match.group(1)), PAYLOAD)
    return refs


def _collect_python_refs(root: Path) -> dict[str, set[str]]:
    """W9: images named in Python. 33 MB of live weight hid here."""
    refs: dict[str, set[str]] = {}
    for path in root.rglob("*.py"):
        parts = set(path.parts)
        if parts & PY_SKIP_PARTS or path.name in PY_SKIP_NAMES:
            continue
        if path.name.startswith("test_") or path.name == "tests.py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        kind = SOCIAL if path.name in PY_SOCIAL_NAMES else PAYLOAD
        for match in PY_REF.finditer(text):
            _add(refs, _normalize_ref(match.group(1)), kind)
    return refs


def collect_all_refs(root: Path) -> dict[str, set[str]]:
    merged: dict[str, set[str]] = {}
    for source in (
        _collect_template_refs(root / "templates"),
        _collect_css_refs(root / "static" / "css"),
        _collect_python_refs(root),
    ):
        for rel, kinds in source.items():
            merged.setdefault(rel, set()).update(kinds)
    return merged


def _verdict(kinds: set[str]) -> str:
    """Referenced as real payload anywhere means it is real payload.

    Precedence matters: a file used as a bare <img> on one page and as a
    <picture> fallback on another is payload, because one page really does
    download it. Social-only is the weakest claim of all.
    """
    if PAYLOAD in kinds:
        return PAYLOAD
    return FALLBACK if FALLBACK in kinds else SOCIAL


class ReferencedStaticImageWeightTests(SimpleTestCase):
    """Fail if any image a browser actually fetches exceeds its byte cap."""

    def test_all_three_surfaces_are_being_scanned(self):
        """Self-check: a guard that silently stops scanning is worse than none.

        Each assertion below corresponds to a surface that once shipped weight
        nobody was watching. If one of them ever finds nothing, the guard has
        gone blind on that surface and this test says which.
        """
        root = Path(settings.BASE_DIR)
        self.assertTrue(
            _collect_template_refs(root / "templates"),
            "template {% static %} scan found nothing — guard is blind",
        )
        self.assertTrue(
            _collect_css_refs(root / "static" / "css"),
            "CSS url() scan found nothing — guard is blind again (W3-FIX)",
        )
        self.assertTrue(
            _collect_python_refs(root),
            "Python image-path scan found nothing — guard is blind again (W9)",
        )

    def test_payload_images_under_byte_caps(self):
        root = Path(settings.BASE_DIR)
        static_root = root / "static"
        self.assertTrue(static_root.is_dir())

        offenders: list[str] = []
        for rel, kinds in sorted(collect_all_refs(root).items()):
            if _verdict(kinds) != PAYLOAD:
                continue
            path = static_root / rel
            if not path.is_file():
                continue
            size = path.stat().st_size
            cap, reason = _cap_for(rel)
            if size > cap:
                offenders.append(f"{rel}: {size} B > cap {cap} B ({reason})")

        if offenders:
            self.fail(
                "Image(s) a browser actually downloads exceed their byte cap. "
                "Shrink them, or disconnect them — never delete.\n"
                + "\n".join(offenders)
            )

    def test_non_payload_refs_stay_sane(self):
        """<picture> fallbacks and og:image targets are not page downloads.

        They still get a ceiling, because something absurd parked there is
        worth knowing about — just not at the same severity as live weight.
        """
        root = Path(settings.BASE_DIR)
        static_root = root / "static"

        offenders: list[str] = []
        for rel, kinds in sorted(collect_all_refs(root).items()):
            if _verdict(kinds) == PAYLOAD:
                continue
            path = static_root / rel
            if not path.is_file():
                continue
            size = path.stat().st_size
            if size > FALLBACK_CEILING:
                offenders.append(f"{rel}: {size} B > fallback ceiling {FALLBACK_CEILING} B")

        if offenders:
            self.fail(
                "<picture> fallback(s) beyond the sanity ceiling:\n" + "\n".join(offenders)
            )
