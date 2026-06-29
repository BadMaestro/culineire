"""
Generate watercolour portrait avatars for each Chef Battle rank.

Usage:
  python manage.py generate_rank_avatars
  python manage.py generate_rank_avatars --force
  python manage.py generate_rank_avatars --rank porter
"""

import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from recipes.management.commands.generate_recipe import fetch_image_bytes  # noqa: E402

BASE_STYLE = (
    "Detailed watercolour and ink illustration, circular portrait composition on "
    "cream parchment background, Irish coastal cliffs and sea visible behind the "
    "figure, warm muted earth tones, auburn or dark hair, fine cross-hatching "
    "detail, editorial illustration quality, no text, no labels, 1:1 square format."
)

RANK_PROMPTS = {
    "porter": (
        "A young kitchen worker in worn white uniform, arms full carrying a tall "
        "precarious stack of clean plates, a wet mop propped against the wall "
        "beside them, exhausted but proud expression, back-of-house stone wall background. "
        + BASE_STYLE
    ),
    "prep": (
        "A focused cook at a heavy wooden chopping board, both hands on a chef's "
        "knife making precise cuts through a pile of fresh vegetables, sleeves "
        "rolled up, intense concentration on their face, mise en place bowls "
        "arranged around them. "
        + BASE_STYLE
    ),
    "commis": (
        "A young chef at a professional stove confidently tossing a pan with one "
        "hand, food mid-air above the flame, white jacket slightly splattered, "
        "eyes alert and focused on the pan, first real kitchen station moment. "
        + BASE_STYLE
    ),
    "partie": (
        "A skilled chef leaning over a pristine white plate, holding fine tweezers "
        "with absolute precision, placing a single small garnish on an elegant "
        "dish, expression of total concentration and pride, their station "
        "immaculate around them. "
        + BASE_STYLE
    ),
    "sous": (
        "A commanding chef standing slightly back from the pass, arms folded, "
        "watching over a busy kitchen, calm authoritative expression, other cooks "
        "visible as blurred figures in motion behind them, tall toque. "
        + BASE_STYLE
    ),
    "head": (
        "A head chef tasting from a large ladle held up to their lips, one hand "
        "held behind their back in classic chef posture, eyes half-closed in "
        "concentration judging the flavour, pristine whites, absolute authority "
        "in their posture, full kitchen brigade visible behind. "
        + BASE_STYLE
    ),
    "exec": (
        "An executive chef in double-breasted whites standing at the pass of a "
        "grand kitchen, surveying the operation with quiet authority, arms loosely "
        "behind back, a small brigade pin or medal visible on their chest, "
        "multiple kitchen stations visible behind. "
        + BASE_STYLE
    ),
    "master": (
        "A legendary older chef, silver at the temples, triumphantly raising a "
        "single beautifully plated dish above their head with both hands, radiant "
        "warm light around the dish, expression of hard-earned joy and pride, "
        "Irish coastline glowing at golden hour behind them, a subtle crown motif "
        "worked into the composition. "
        + BASE_STYLE
    ),
}


class Command(BaseCommand):
    help = "Generate watercolour rank avatar images for Chef Battle rank ladder"

    def add_arguments(self, parser):
        parser.add_argument(
            "--rank",
            choices=list(RANK_PROMPTS.keys()),
            default=None,
            help="Generate only this rank (omit for all 8)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Re-generate even if file already exists",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "OPENAI_API_KEY", ""):
            raise CommandError("OPENAI_API_KEY is not set.")

        dest_dir = Path(settings.BASE_DIR) / "chef_battle" / "static" / "chef_battle" / "images" / "ranks"
        dest_dir.mkdir(parents=True, exist_ok=True)

        force = options["force"]
        rank_filter = options.get("rank")
        prompts = {k: v for k, v in RANK_PROMPTS.items() if not rank_filter or k == rank_filter}

        for slug, prompt in prompts.items():
            dest = dest_dir / f"chef-rank-{slug}.png"
            if dest.exists() and not force:
                self.stdout.write(f"  skip  chef-rank-{slug}.png")
                continue
            self.stdout.write(f"  gen   chef-rank-{slug} ...", ending="")
            self.stdout.flush()
            try:
                data = fetch_image_bytes(prompt)
                dest.write_bytes(data)
                self.stdout.write(self.style.SUCCESS(f" ok ({len(data)//1024}kb)"))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f" FAIL: {exc}"))

        self.stdout.write(self.style.SUCCESS("Done."))
