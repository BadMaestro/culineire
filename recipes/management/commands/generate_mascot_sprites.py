"""
Generate GreenBear chef mascot sprite strips for the hero animation.

Generates 8 individual frames via OpenAI image API, then composes them into
two 4-frame horizontal sprite strips:

  hero-chef.webp       — idle, look, sharpen, egg-toss  (main sprite)
  hero-chef-walk.webp  — 4 walking frames               (walk sprite)

Usage:
  python manage.py generate_mascot_sprites
  python manage.py generate_mascot_sprites --force
  python manage.py generate_mascot_sprites --only walk
  python manage.py generate_mascot_sprites --only main
"""

import io
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from recipes.management.commands.generate_recipe import fetch_image_bytes  # noqa: E402

# Output sprite dimensions — must match existing CSS expectations
FRAME_W = 310
FRAME_H = 496
STRIP_FRAMES = 4

# GreenBear character base description (reused in every prompt)
CHAR_BASE = (
    "cartoon mascot character, a friendly green bear wearing a tall white chef hat "
    "and a dark brown leather jacket over a chef's apron, thick rounded body, "
    "short stubby legs, small round ears, warm friendly face with large eyes, "
    "flat 2D illustration style with clean outlines, fully transparent background, "
    "character centred and fully visible from head to toe, no shadows on background, "
    "PNG with alpha channel, no text, no watermark"
)

WALK_PROMPTS = [
    # Frame 0 — right leg forward, arms swinging
    (
        "green bear chef mascot walking left, right leg stepping forward, left arm "
        "swung forward, right arm back, mid-stride pose, weight on left foot, "
        f"{CHAR_BASE}"
    ),
    # Frame 1 — upright passing position
    (
        "green bear chef mascot walking left, both feet close together, upright "
        "neutral mid-walk position, arms at sides, weight evenly distributed, "
        f"{CHAR_BASE}"
    ),
    # Frame 2 — left leg forward, arms opposite
    (
        "green bear chef mascot walking left, left leg stepping forward, right arm "
        "swung forward, left arm back, mid-stride pose, weight on right foot, "
        f"{CHAR_BASE}"
    ),
    # Frame 3 — upright passing position (slight variation)
    (
        "green bear chef mascot walking left, both feet close together, upright "
        "relaxed mid-walk position, arms loosely swinging, weight shifting right, "
        f"{CHAR_BASE}"
    ),
]

MAIN_PROMPTS = [
    # Frame 0 — idle (background-position 0%)
    (
        "green bear chef mascot standing idle, arms relaxed at sides, slight "
        "friendly smile, upright resting pose facing slightly left, "
        f"{CHAR_BASE}"
    ),
    # Frame 1 — looking around / curious (33.3%)
    (
        "green bear chef mascot peering curiously to the left, one hand raised "
        "to shade eyes as if looking into the distance, curious expression, "
        f"{CHAR_BASE}"
    ),
    # Frame 2 — sharpening knife (66.6%)
    (
        "green bear chef mascot sharpening a large kitchen knife on a whetstone "
        "rod, both hands gripping tools, focused determined expression, elbows "
        "raised, dramatic pose, "
        f"{CHAR_BASE}"
    ),
    # Frame 3 — egg toss (100%)
    (
        "green bear chef mascot tossing an egg in the air with one hand, looking "
        "up at the egg, other hand on hip, playful confident expression, "
        f"{CHAR_BASE}"
    ),
]


def _compose_strip(frames_bytes: list[bytes], label: str) -> bytes:
    """Resize 4 raw image bytes and compose into a horizontal strip WebP."""
    from PIL import Image

    strip = Image.new("RGBA", (FRAME_W * STRIP_FRAMES, FRAME_H), (0, 0, 0, 0))
    for i, raw in enumerate(frames_bytes):
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        # Fit frame preserving aspect ratio — pad with transparency
        img.thumbnail((FRAME_W, FRAME_H), Image.LANCZOS)
        x_off = i * FRAME_W + (FRAME_W - img.width) // 2
        y_off = FRAME_H - img.height
        strip.paste(img, (x_off, y_off), img)

    buf = io.BytesIO()
    strip.save(buf, format="WEBP", lossless=False, quality=85, method=6)
    return buf.getvalue()


class Command(BaseCommand):
    help = "Generate GreenBear chef mascot sprite strips via OpenAI image API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Re-generate even if the output file already exists",
        )
        parser.add_argument(
            "--only",
            choices=["walk", "main"],
            default=None,
            help="Generate only 'walk' or 'main' sprite strip",
        )

    def handle(self, *args, **options):
        dest_dir = Path(__file__).resolve().parents[4] / "static" / "images" / "mascot"
        dest_dir.mkdir(parents=True, exist_ok=True)

        force = options["force"]
        only = options["only"]

        tasks = []
        if only in (None, "walk"):
            tasks.append(("walk", WALK_PROMPTS, dest_dir / "hero-chef-walk.webp"))
        if only in (None, "main"):
            tasks.append(("main", MAIN_PROMPTS, dest_dir / "hero-chef.webp"))

        for label, prompts, dest in tasks:
            if dest.exists() and not force:
                self.stdout.write(self.style.WARNING(
                    f"  skip  {dest.name} (already exists — use --force to regenerate)"
                ))
                continue

            self.stdout.write(f"\n[{label}] Generating {len(prompts)} frames …")
            frames = []
            for idx, prompt in enumerate(prompts):
                self.stdout.write(f"  frame {idx} …", ending="")
                self.stdout.flush()
                try:
                    data = fetch_image_bytes(prompt)
                    frames.append(data)
                    self.stdout.write(self.style.SUCCESS(f" ok ({len(data) // 1024}kb)"))
                except Exception as exc:
                    raise CommandError(f"Frame {idx} failed: {exc}") from exc

            self.stdout.write(f"  composing strip …", ending="")
            self.stdout.flush()
            strip_bytes = _compose_strip(frames, label)
            dest.write_bytes(strip_bytes)
            self.stdout.write(self.style.SUCCESS(
                f" saved {dest.name} ({len(strip_bytes) // 1024}kb)"
            ))

        self.stdout.write(self.style.SUCCESS("\nDone."))
