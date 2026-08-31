"""Burn the house watermark into the sticker shop window and the shelf tiles.

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

#: The picker tiles and full stickers the CHAT uses. Sources only -
#: nothing here is ever written to. Marking the file the chat SENDS would
#: put the watermark inside every message a buyer paid to send, which is
#: not protecting the goods, it is damaging them.
CHAT_FULL_DIR = os.path.join(
    "static", "images", "chef_battle", "arena", "stickers")
CHAT_TILE_DIR = os.path.join(CHAT_FULL_DIR, "tile")

#: The marked copies the SHOP SHELF uses - the gallery is the shop, the
#: chat is the product. A separate folder so a glob can never confuse the
#: two, and so the existing sticker guards keep globbing what they always
#: globbed.
SHELF_FULL_DIR = os.path.join(CHAT_FULL_DIR, "shop")
SHELF_TILE_DIR = os.path.join(SHELF_FULL_DIR, "tile")

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
            self.shelf(root, check=True)
            self.stdout.write("shop window and shelf are watermarked and current")
            return

        with open(target, "wb") as handle:
            handle.write(fresh)
        self.stdout.write(
            f"watermarked {os.path.basename(target)}: {len(fresh)} bytes")

        written = self.shelf(root, check=False)
        self.stdout.write(f"watermarked {written} shelf files")

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


    # ------------------------------------------------------------------ shelf

    def shelf(self, root, *, check):
        """The gallery's own marked copies, in both sizes.

        BOTH SIZES, because the Owner asked for two things at once: the shelf
        shows the small tile, and clicking it opens the sticker in colour. Mark
        only the tile and that click hands over the clean full-size file,
        undoing the whole exercise.

        The chat's files are read and never written. The marked copies live in
        `stickers/shop/`, which no existing guard globs - ArenaChatStickerTests
        pairs `stickers/*.webp` with `stickers/tile/*.webp` and would read a
        third set of files as a sticker with no tile.
        """
        from PIL import Image

        pairs = (
            (os.path.join(root, CHAT_FULL_DIR), os.path.join(root, SHELF_FULL_DIR)),
            (os.path.join(root, CHAT_TILE_DIR), os.path.join(root, SHELF_TILE_DIR)),
        )
        written = 0
        for source_dir, out_dir in pairs:
            if not check:
                os.makedirs(out_dir, exist_ok=True)
            for name in sorted(os.listdir(source_dir)):
                if not name.endswith(".webp"):
                    continue
                with Image.open(os.path.join(source_dir, name)) as art:
                    art.load()
                    marked = self.mark_transparent(art)
                fresh = self.encode_sticker(marked)
                out = os.path.join(out_dir, name)
                if check:
                    if not os.path.exists(out):
                        raise CommandError(f"the shelf is missing {name}")
                    with open(out, "rb") as handle:
                        current = handle.read()
                    if (hashlib.sha256(current).hexdigest()
                            != hashlib.sha256(fresh).hexdigest()):
                        raise CommandError(
                            f"the shelf copy of {name} is stale. Run "
                            f"manage.py watermark_shop_window."
                        )
                else:
                    with open(out, "wb") as handle:
                        handle.write(fresh)
                written += 1
        return written

    def mark_transparent(self, art):
        """A sticker with the mark over it, TRANSPARENCY PRESERVED.

        The sheet is a rectangle on a dark card; a sticker is a cut-out shape
        with an alpha channel. Flattening it here would put a grey box behind
        every tile on the shelf, so the mark is composited onto the RGBA image
        and the alpha survives.

        AND THE MARK IS CLIPPED TO THE ARTWORK. Its own alpha is taken as the
        darker of itself and the sticker's, so the lattice appears only where
        the sticker is opaque and never floats in the empty corners around the
        cut-out - which is both what it should look like and what stops the
        mark from advertising the shape of the transparency.
        """
        from PIL import Image, ImageChops, ImageDraw

        rgba = art.convert("RGBA")
        width, height = rgba.size
        font = self.font(max(9, width // 11))

        span = int((width ** 2 + height ** 2) ** 0.5) + 12
        layer = Image.new("RGBA", (span, span), (0, 0, 0, 0))
        pen = ImageDraw.Draw(layer)
        box = pen.textbbox((0, 0), MARK, font=font)
        step_x = (box[2] - box[0]) + max(10, width // 8)
        step_y = (box[3] - box[1]) + max(10, height // 5)

        # HEAVIER THAN THE SHEET'S 0.17, AND THE SHADOW CARRIES EQUAL WEIGHT.
        # The sheet is one dark card, so white at 0.17 reads across all of it.
        # A sticker is not: YES CHEF! is a bright yellow burst and SEARED is
        # near-black, and a white mark that reads on the second vanishes on the
        # first - measured, on this exact file, at 0.30 with a half-strength
        # shadow. Two strokes of equal weight, white over dark, give a mark
        # that survives both, and 0.42 survives the browser drawing a 160px
        # tile smaller still.
        ink = int(255 * 0.42)
        for row, y in enumerate(range(0, span, step_y)):
            offset = (step_x // 2) if row % 2 else 0
            for x in range(-step_x, span, step_x):
                pen.text((x + offset, y), MARK, font=font,
                         fill=(255, 255, 255, ink))
                pen.text((x + offset + 1, y + 1), MARK, font=font,
                         fill=(0, 0, 0, ink))

        layer = layer.rotate(ANGLE, resample=Image.BICUBIC)
        left = (span - width) // 2
        top = (span - height) // 2
        layer = layer.crop((left, top, left + width, top + height))
        layer.putalpha(ImageChops.darker(layer.split()[3], rgba.split()[3]))

        out = rgba.copy()
        out.alpha_composite(layer)
        return out

    def encode_sticker(self, image):
        import io

        buffer = io.BytesIO()
        # Lossless would double the size of art that already ships lossy. 82
        # keeps a marked tile inside the 20 KB tile cap and a marked full
        # sticker inside the 60 KB one - both measured, not assumed.
        image.save(buffer, "WEBP", quality=82, method=6)
        return buffer.getvalue()

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
