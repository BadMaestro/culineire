"""
Generate GreenBear chef mascot sprite strips for the hero animation.

Each strip is generated as a SINGLE image request (all 4 frames side by side
in one 1024×1024 canvas) so that OpenAI renders the character consistently
across all frames. The resulting image is then sliced into individual frames.

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

# GreenBear character definition — used in both strip prompts
CHAR_DEF = (
    "IMPORTANT: The character MUST be an anthropomorphic BEAR — not a human, not a person. "
    "A cartoon bear standing upright on two legs, with a bear's snout, bear nose, round bear ears on top of the head, "
    "bear paws as hands, green fur all over the body. "
    "The bear wears a tall white chef toque hat, a dark brown leather jacket, and a white chef's apron. "
    "Big friendly eyes, wide smile showing small teeth, chubby round bear belly, short stubby bear legs. "
    "Flat 2D cartoon illustration style, clean black outlines, vibrant green fur colour. "
    "Do NOT draw a human. This is a green cartoon bear."
)

# Single-image prompt for the walk sprite strip
WALK_STRIP_PROMPT = (
    "A horizontal sprite sheet of a green anthropomorphic cartoon bear chef walking. "
    "NOT a human — this is a cartoon BEAR with green fur, bear snout, round bear ears, bear paws. "
    "The bear wears a tall white chef hat, dark leather jacket, white apron. "
    "Exactly 4 frames in a single horizontal row, evenly spaced, each frame the same width. "
    "All frames face left. "
    "Frame 1: bear mid-stride, one paw forward. "
    "Frame 2: bear upright, both feet together. "
    "Frame 3: bear mid-stride opposite leg forward. "
    "Frame 4: bear upright, slightly different arm position. "
    "Transparent background, full body visible in each frame, no text, no labels, no border. "
    f"{CHAR_DEF}"
)

# Single-image prompt for the main sprite strip
MAIN_STRIP_PROMPT = (
    "A horizontal sprite sheet of a green anthropomorphic cartoon bear chef in 4 poses. "
    "NOT a human — this is a cartoon BEAR with green fur, bear snout, round bear ears, bear paws. "
    "The bear wears a tall white chef hat, dark leather jacket, white apron. "
    "Exactly 4 poses in a single horizontal row, evenly spaced, each pose the same width. "
    "Pose 1: bear standing idle, arms relaxed, friendly smile. "
    "Pose 2: bear looking left curiously, one paw raised to shade eyes. "
    "Pose 3: bear sharpening a kitchen knife on a steel rod, both paws raised. "
    "Pose 4: bear tossing an egg in the air, looking up at it, other paw on hip. "
    "Transparent background, full body visible in each pose, no text, no labels, no border. "
    f"{CHAR_DEF}"
)


def _slice_strip(raw: bytes, out_w: int, out_h: int, n: int) -> bytes:
    """Slice a generated sprite-sheet image into n equal columns, resize, save as WebP."""
    from PIL import Image

    src = Image.open(io.BytesIO(raw)).convert("RGBA")
    sw, sh = src.size
    col_w = sw // n

    strip = Image.new("RGBA", (out_w * n, out_h), (0, 0, 0, 0))
    for i in range(n):
        frame = src.crop((i * col_w, 0, (i + 1) * col_w, sh))
        frame.thumbnail((out_w, out_h), Image.LANCZOS)
        x_off = i * out_w + (out_w - frame.width) // 2
        y_off = out_h - frame.height
        strip.paste(frame, (x_off, y_off), frame)

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
            tasks.append(("walk", WALK_STRIP_PROMPT, dest_dir / "hero-chef-walk.webp"))
        if only in (None, "main"):
            tasks.append(("main", MAIN_STRIP_PROMPT, dest_dir / "hero-chef.webp"))

        for label, prompt, dest in tasks:
            if dest.exists() and not force:
                self.stdout.write(self.style.WARNING(
                    f"  skip  {dest.name} (already exists — use --force to regenerate)"
                ))
                continue

            self.stdout.write(f"\n[{label}] Generating sprite sheet …", ending="")
            self.stdout.flush()
            try:
                raw = fetch_image_bytes(prompt)
                self.stdout.write(self.style.SUCCESS(f" ok ({len(raw) // 1024}kb)"))
            except Exception as exc:
                raise CommandError(f"[{label}] generation failed: {exc}") from exc

            self.stdout.write(f"  slicing and composing strip …", ending="")
            self.stdout.flush()
            strip_bytes = _slice_strip(raw, FRAME_W, FRAME_H, STRIP_FRAMES)
            dest.write_bytes(strip_bytes)
            self.stdout.write(self.style.SUCCESS(
                f" saved {dest.name} ({len(strip_bytes) // 1024}kb)"
            ))

        self.stdout.write(self.style.SUCCESS("\nDone."))
