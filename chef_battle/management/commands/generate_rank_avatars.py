"""
Generate watercolour portrait avatars for each Chef Battle rank.

Usage:
  python manage.py generate_rank_avatars
  python manage.py generate_rank_avatars --force
  python manage.py generate_rank_avatars --rank porter
  python manage.py generate_rank_avatars --gender female
  python manage.py generate_rank_avatars --gender neutral
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
    "male": {
        "porter": (
            "A young male kitchen worker in worn white uniform, arms full carrying a tall "
            "precarious stack of clean plates, a wet mop propped against the wall "
            "beside them, exhausted but proud expression, back-of-house stone wall background. "
            + BASE_STYLE
        ),
        "prep": (
            "A focused male cook at a heavy wooden chopping board, both hands on a chef's "
            "knife making precise cuts through a pile of fresh vegetables, sleeves "
            "rolled up, intense concentration on their face, mise en place bowls "
            "arranged around them. "
            + BASE_STYLE
        ),
        "commis": (
            "A young male chef at a professional stove confidently tossing a pan with one "
            "hand, food mid-air above the flame, white jacket slightly splattered, "
            "eyes alert and focused on the pan, first real kitchen station moment. "
            + BASE_STYLE
        ),
        "partie": (
            "A skilled male chef leaning over a pristine white plate, holding fine tweezers "
            "with absolute precision, placing a single small garnish on an elegant "
            "dish, expression of total concentration and pride, their station "
            "immaculate around them. "
            + BASE_STYLE
        ),
        "sous": (
            "A commanding male chef standing slightly back from the pass, arms folded, "
            "watching over a busy kitchen, calm authoritative expression, other cooks "
            "visible as blurred figures in motion behind them, tall toque. "
            + BASE_STYLE
        ),
        "head": (
            "A male head chef tasting from a large ladle held up to their lips, one hand "
            "held behind their back in classic chef posture, eyes half-closed in "
            "concentration judging the flavour, pristine whites, absolute authority "
            "in their posture, full kitchen brigade visible behind. "
            + BASE_STYLE
        ),
        "exec": (
            "A male executive chef in double-breasted whites standing at the pass of a "
            "grand kitchen, surveying the operation with quiet authority, arms loosely "
            "behind back, a small brigade pin or medal visible on their chest, "
            "multiple kitchen stations visible behind. "
            + BASE_STYLE
        ),
        "master": (
            "A legendary older male chef, silver at the temples, triumphantly raising a "
            "single beautifully plated dish above their head with both hands, radiant "
            "warm light around the dish, expression of hard-earned joy and pride, "
            "Irish coastline glowing at golden hour behind them, a subtle crown motif "
            "worked into the composition. "
            + BASE_STYLE
        ),
    },
    "female": {
        "porter": (
            "A young woman in worn white uniform, arms full carrying a tall "
            "precarious stack of clean plates, a wet mop propped against the wall "
            "beside her, exhausted but proud expression, hair tied back neatly, "
            "back-of-house stone wall background. "
            + BASE_STYLE
        ),
        "prep": (
            "A focused woman at a heavy wooden chopping board, both hands on a chef's "
            "knife making precise cuts through a pile of fresh vegetables, sleeves "
            "rolled up, intense concentration on her face, mise en place bowls "
            "arranged around her, hair in a neat bun. "
            + BASE_STYLE
        ),
        "commis": (
            "A young woman at a professional stove confidently tossing a pan with one "
            "hand, food mid-air above the flame, white jacket slightly splattered, "
            "eyes alert and focused on the pan, first real kitchen station moment, "
            "hair pinned back. "
            + BASE_STYLE
        ),
        "partie": (
            "A skilled woman leaning over a pristine white plate, holding fine tweezers "
            "with absolute precision, placing a single small garnish on an elegant "
            "dish, expression of total concentration and pride, her station "
            "immaculate around her. "
            + BASE_STYLE
        ),
        "sous": (
            "A commanding woman standing slightly back from the pass, arms folded, "
            "watching over a busy kitchen, calm authoritative expression, other cooks "
            "visible as blurred figures in motion behind her, tall toque, natural "
            "authority in her posture. "
            + BASE_STYLE
        ),
        "head": (
            "A female head chef tasting from a large ladle held up to her lips, one hand "
            "held behind her back in classic chef posture, eyes half-closed in "
            "concentration judging the flavour, pristine whites, absolute authority "
            "in her posture, full kitchen brigade visible behind. "
            + BASE_STYLE
        ),
        "exec": (
            "A female executive chef in double-breasted whites standing at the pass of a "
            "grand kitchen, surveying the operation with quiet authority, arms loosely "
            "behind back, a small brigade pin or medal visible on her chest, "
            "multiple kitchen stations visible behind, commanding presence. "
            + BASE_STYLE
        ),
        "master": (
            "A legendary older female chef, silver streaks in her hair, triumphantly raising a "
            "single beautifully plated dish above her head with both hands, radiant "
            "warm light around the dish, expression of hard-earned joy and pride, "
            "Irish coastline glowing at golden hour behind her, a subtle crown motif "
            "worked into the composition. "
            + BASE_STYLE
        ),
    },
    "neutral": {
        "porter": (
            "A young androgynous kitchen worker in worn white uniform, arms full carrying "
            "a tall precarious stack of clean plates, a wet mop propped against the wall "
            "beside them, exhausted but proud expression, short neat hair, "
            "back-of-house stone wall background. "
            + BASE_STYLE
        ),
        "prep": (
            "An androgynous cook at a heavy wooden chopping board, both hands on a chef's "
            "knife making precise cuts through a pile of fresh vegetables, sleeves "
            "rolled up, intense concentration on their face, mise en place bowls "
            "arranged around them, neat short hair. "
            + BASE_STYLE
        ),
        "commis": (
            "A young androgynous chef at a professional stove confidently tossing a pan "
            "with one hand, food mid-air above the flame, white jacket slightly splattered, "
            "eyes alert and focused on the pan, short cropped hair, serene focus. "
            + BASE_STYLE
        ),
        "partie": (
            "An androgynous chef leaning over a pristine white plate, holding fine tweezers "
            "with absolute precision, placing a single small garnish on an elegant "
            "dish, expression of total concentration and pride, short neat hair, "
            "their station immaculate around them. "
            + BASE_STYLE
        ),
        "sous": (
            "An androgynous chef standing slightly back from the pass, arms folded, "
            "watching over a busy kitchen, calm authoritative expression, other cooks "
            "visible as blurred figures in motion behind them, tall toque, short neat hair. "
            + BASE_STYLE
        ),
        "head": (
            "An androgynous head chef tasting from a large ladle held up to their lips, "
            "one hand held behind their back in classic chef posture, eyes half-closed in "
            "concentration judging the flavour, pristine whites, absolute authority "
            "in their posture, short cropped hair, full kitchen brigade visible behind. "
            + BASE_STYLE
        ),
        "exec": (
            "An androgynous executive chef in double-breasted whites standing at the pass "
            "of a grand kitchen, surveying the operation with quiet authority, arms loosely "
            "behind back, a small brigade pin or medal visible on their chest, "
            "short neat hair, multiple kitchen stations visible behind. "
            + BASE_STYLE
        ),
        "master": (
            "A legendary androgynous chef, silver at the temples, short elegant hair, "
            "triumphantly raising a single beautifully plated dish above their head with "
            "both hands, radiant warm light around the dish, expression of hard-earned joy "
            "and pride, Irish coastline glowing at golden hour behind them, a subtle crown "
            "motif worked into the composition. "
            + BASE_STYLE
        ),
    },
}

RANK_SLUGS = ["porter", "prep", "commis", "partie", "sous", "head", "exec", "master"]
GENDERS = ["male", "female", "neutral"]


class Command(BaseCommand):
    help = "Generate watercolour rank avatar images for Chef Battle rank ladder"

    def add_arguments(self, parser):
        parser.add_argument(
            "--rank",
            choices=RANK_SLUGS,
            default=None,
            help="Generate only this rank (omit for all 8)",
        )
        parser.add_argument(
            "--gender",
            choices=GENDERS,
            default=None,
            help="Generate only this gender variant (omit for all 3)",
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
        gender_filter = options.get("gender")

        genders = [gender_filter] if gender_filter else GENDERS

        for gender in genders:
            prompts = RANK_PROMPTS[gender]
            for slug in RANK_SLUGS:
                if rank_filter and slug != rank_filter:
                    continue
                prompt = prompts[slug]
                suffix = "" if gender == "male" else f"-{gender}"
                dest = dest_dir / f"chef-rank-{slug}{suffix}.png"
                if dest.exists() and not force:
                    self.stdout.write(f"  skip  chef-rank-{slug}{suffix}.png")
                    continue
                self.stdout.write(f"  gen   chef-rank-{slug}{suffix} ...", ending="")
                self.stdout.flush()
                try:
                    data = fetch_image_bytes(prompt)
                    dest.write_bytes(data)
                    self.stdout.write(self.style.SUCCESS(f" ok ({len(data)//1024}kb)"))
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f" FAIL: {exc}"))

        self.stdout.write(self.style.SUCCESS("Done."))
