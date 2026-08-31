"""Burn the house watermark into the sticker shop window.

Owner, 2026-08-30: "теперь водяной знак на витрину".

WHY THIS IS A COMMAND AND NOT AN EDIT. The sheet is his own artwork, placed
and never redrawn (Carpet #3552). Painting over the file by hand would destroy
the original and leave nobody able to say what the mark was or undo it. This
reads a PRISTINE source that is kept out of the published tree and writes the
marked copy that the page actually serves, so the original survives, the mark
is reproducible, and changing it is one edit and one re-run.

WHY THE MARK IS BURNED IN RATHER THAN LAID OVER IN CSS. A CSS overlay appears
in a screenshot, which is half the job - and disappears entirely the moment
somebody opens the image in a new tab or fetches the URL, which is the other
half. The shop window is a public static file; whatever protects it has to be
in the pixels.

WHY IT IS TILED DIAGONALLY. A corner mark is defeated by a 5% crop. A repeated
diagonal lattice means any crop large enough to be worth taking still carries
at least one full mark. This is the one property that distinguishes a watermark
from a signature.

WHAT IT HONESTLY DOES. It does not stop a determined person: automated
inpainting removes a visible mark, and that is published, free and fast. What it
does is make the unprocessed copy - the one somebody actually screenshots and
posts - carry the shop's name. Anything better than that costs more than the
pack it protects.

    manage.py watermark_shop_window            # writes the marked file
    manage.py watermark_shop_window --check    # verifies it is current, writes nothing
"""
from __future__ import annotations

import hashlib
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

#: The Owner's original, kept OUT of static/ so it is never served. Moving it
#: here rather than deleting it is the rule for anything he approved: it stays
#: in git, one directory away, and the marked copy can always be rebuilt.
SOURCE = os.path.join("ops", "reference", "stickers", "sticker_pack_arena_2026.webp")

#: What the page serves.
TARGET = os.path.join(
    "static", "images", "chef_battle", "sticker_pack_arena_2026.webp")

MARK = "culineire.ie"
#: Opacity of the mark. Measured by eye against the sheet: below 0.10 it stops
#: surviving a screenshot re-scale, above 0.20 it starts competing with the
#: artwork it is advertising. This is the shop window - it has to sell.
ALPHA = 0.17
ANGLE = 30


class Command(BaseCommand):
    help = "Burn the house watermark into the sticker pack shop window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check", action="store_true",
            help="Verify the served file matches the source plus the mark.",
        )

    def handle(self, *args, **options):
        from PIL import Image

        root = str(settings.BASE_DIR)
        source = os.path.join(root, SOURCE)
        target = os.path.join(root, TARGET)

        if not os.path.exists(source):
            raise CommandError(
                f"the pristine sheet is missing: {SOURCE}. It is the Owner's "
                f"artwork - restore it from git rather than regenerating it."
            )

        with Image.open(source) as art:
            art.load()
            marked = self.mark(art.convert("RGB"))

        fresh = self.encode(marked)

        if options["check"]:
            if not os.path.exists(target):
                raise CommandError(f"{TARGET} does not exist")
            with open(target, "rb") as handle:
                current = handle.read()
            if hashlib.sha256(current).hexdigest() != hashlib.sha256(fresh).hexdigest():
                raise CommandError(
                    f"{TARGET} is not the current watermark of {SOURCE}. "
                    f"Run manage.py watermark_shop_window."
                )
            self.stdout.write("shop window is watermarked and current")
            return

        with open(target, "wb") as handle:
            handle.write(fresh)
        self.stdout.write(
            f"watermarked {os.path.basename(target)}: {len(fresh)} bytes")

    # ---------------------------------------------------------------- marking

    def mark(self, art):
        """The sheet with a tiled diagonal `culineire.ie` woven through it."""
        from PIL import Image, ImageDraw, ImageFont

        width, height = art.size
        font = self.font(max(16, width // 26))

        # Drawn on a canvas larger than the sheet and rotated, so the lattice
        # runs off every edge instead of stopping short of the corners.
        span = int((width ** 2 + height ** 2) ** 0.5) + 40
        layer = Image.new("RGBA", (span, span), (0, 0, 0, 0))
        pen = ImageDraw.Draw(layer)

        box = pen.textbbox((0, 0), MARK, font=font)
        # SPACED TO THE CROP THAT IS WORTH TAKING. The thing somebody
        # actually cuts out of this sheet is one sticker cell, about
        # 200x190 on a 900x675 sheet - so the lattice has to be tighter
        # than that or a single-sticker crop comes away clean. Measured on
        # the real file: at width//8 the horizontal gap was 224px and a
        # cell could fall between two marks.
        step_x = (box[2] - box[0]) + max(28, width // 14)
        step_y = (box[3] - box[1]) + max(26, height // 12)

        ink = int(255 * ALPHA)
        for row, y in enumerate(range(0, span, step_y)):
            # Every other row is offset by half a step: a square grid reads as
            # a pattern of holes a crop can be aimed between.
            offset = (step_x // 2) if row % 2 else 0
            for x in range(-step_x, span, step_x):
                pen.text((x + offset, y), MARK, font=font,
                         fill=(255, 255, 255, ink))
                pen.text((x + offset + 1, y + 1), MARK, font=font,
                         fill=(0, 0, 0, ink // 2))

        layer = layer.rotate(ANGLE, resample=Image.BICUBIC)
        left = (span - width) // 2
        top = (span - height) // 2
        layer = layer.crop((left, top, left + width, top + height))

        out = art.convert("RGBA")
        out.alpha_composite(layer)
        return out.convert("RGB")

    def font(self, size):
        from PIL import ImageFont

        # A named font first, so the mark looks the same on the workstation and
        # on the server; the bundled default only if the box has neither.
        for candidate in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial_Bold.ttf",
                          "DejaVuSans.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def encode(self, image):
        import io

        buffer = io.BytesIO()
        # QUALITY 78, AND THE NUMBER IS THE IMAGE-WEIGHT GATE'S, NOT A TASTE.
        # The mark adds high-frequency edges everywhere, so the marked sheet
        # encodes larger than the clean one: measured on this file, q88 gives
        # 172 KB against a 150 KB cap for UI chrome, q85 gives 162 KB, q82
        # lands at 149,984 bytes - sixteen bytes of headroom, which is not
        # headroom. q78 is 139 KB and leaves room for the mark or the artwork
        # to change without turning the gate red on somebody else's deploy.
        image.save(buffer, "WEBP", quality=78, method=6)
        return buffer.getvalue()
