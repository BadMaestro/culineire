"""
Generate GreenBear chef mascot sprite strips for the hero animation.

Generates frames individually (one OpenAI call per frame) then composes
into two 4-frame horizontal sprite strips:

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

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from recipes.management.commands.generate_recipe import fetch_image_bytes  # noqa: E402

# Output sprite dimensions — must match existing CSS expectations
FRAME_W = 310
FRAME_H = 496
STRIP_FRAMES = 4

# Core character description — must produce a green cartoon bear, not a human
CHAR = (
    "anthropomorphic cartoon GREEN BEAR standing upright. "
    "NOT a human. A bear: green fur, bear snout, bear nose, round bear ears on top of head, "
    "bear paws as hands. Wears a tall white chef toque hat, dark brown leather jacket, white apron. "
    "Chubby round belly, short stubby legs, large friendly eyes, wide smile. "
    "Facing LEFT. Full body visible. Transparent background. "
    "Flat 2D cartoon style, clean black outlines. No text, no watermark, no shadow on ground."
)

WALK_PROMPTS = [
    f"Cartoon green bear chef walking LEFT, right paw stepping forward, left arm swung back, mid-stride. {CHAR}",
    f"Cartoon green bear chef walking LEFT, both feet close together, upright position, arms at sides. {CHAR}",
    f"Cartoon green bear chef walking LEFT, left paw stepping forward, right arm swung back, opposite stride. {CHAR}",
    f"Cartoon green bear chef walking LEFT, both feet together, slight bounce, arms loosely at sides. {CHAR}",
]

MAIN_PROMPTS = [
    f"Cartoon green bear chef standing idle, arms relaxed at sides, friendly smile, facing LEFT. {CHAR}",
    f"Cartoon green bear chef looking LEFT with curiosity, one paw raised to shade eyes, peering into distance. {CHAR}",
    f"Cartoon green bear chef sharpening a kitchen knife on a steel rod, both paws raised, focused expression, facing LEFT. {CHAR}",
    f"Cartoon green bear chef tossing an egg in the air with one paw, looking up at the egg, other paw on hip, facing LEFT. {CHAR}",
]


def _frame_to_strip_cell(raw: bytes, out_w: int, out_h: int) -> "Image":
    """Convert raw image bytes into a single sprite cell (RGBA, out_w × out_h)."""
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    # Scale to fit within the cell, preserving aspect ratio
    img.thumbnail((out_w, out_h), Image.LANCZOS)
    cell = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    x_off = (out_w - img.width) // 2
    y_off = out_h - img.height  # pin to bottom
    cell.paste(img, (x_off, y_off), img)
    return cell


def _compose_strip(cells) -> bytes:
    """Paste sprite cells into a horizontal strip and encode as WebP."""
    from PIL import Image

    n = len(cells)
    strip = Image.new("RGBA", (FRAME_W * n, FRAME_H), (0, 0, 0, 0))
    for i, cell in enumerate(cells):
        strip.paste(cell, (i * FRAME_W, 0))
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
        dest_dir = Path(settings.BASE_DIR) / "static" / "images" / "mascot"
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
                    f"  skip  {dest.name} (use --force to regenerate)"
                ))
                continue

            self.stdout.write(f"\n[{label}] Generating {len(prompts)} frames …")
            cells = []
            for idx, prompt in enumerate(prompts):
                self.stdout.write(f"  frame {idx} …", ending="")
                self.stdout.flush()
                try:
                    raw = fetch_image_bytes(prompt)
                    cells.append(_frame_to_strip_cell(raw, FRAME_W, FRAME_H))
                    self.stdout.write(self.style.SUCCESS(f" ok ({len(raw) // 1024}kb)"))
                except Exception as exc:
                    raise CommandError(f"Frame {idx} failed: {exc}") from exc

            self.stdout.write(f"  composing strip …", ending="")
            self.stdout.flush()
            strip_bytes = _compose_strip(cells)
            dest.write_bytes(strip_bytes)
            self.stdout.write(self.style.SUCCESS(
                f" saved {dest.name} ({len(strip_bytes) // 1024}kb)"
            ))

        self.stdout.write(self.style.SUCCESS("\nDone."))
