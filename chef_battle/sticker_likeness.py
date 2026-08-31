"""Refuse a chat upload that is one of the shop's own stickers.

Owner, 2026-08-30: "зачем мне их покупать, если я тупо могу скопировать стикер
из чата или даже из галереи в артефактах и тупо вставить в чат как сообщение
или как гиф?"

He is right, and the hole was not where it looked. The ownership check on the
send path (`unowned_sticker_tokens`) guards the TOKEN - `:yes_chef:` typed by
somebody who has not bought it is refused. It knows nothing about a picture,
and the 13 sticker files are ordinary static assets: fetchable with `curl`, no
login, 40KB each. Download one, or copy it out of somebody else's message, and
re-upload it as an ordinary chat image, and the paid product arrives for free
by a route the paywall never watched.

THE UPLOAD PATH IS THE ONE PLACE THIS CAN BE CLOSED, and it is ours. Nothing
prevents the download - the picture has to reach every reader's screen or the
chat does not work - but the picture only becomes a free sticker when it comes
BACK. `normalise_uploaded_chat_media` has already decoded the bytes by then, so
the comparison costs one small resize on an image that is in memory anyway.

WHAT THIS IS NOT. It is not a watermark and not DRM. A screenshot of a sticker
against an unusual background, a heavy crop, a mirror or a strong recolour will
pass - and each of those makes the copy visibly worse than the ten-token
original, which is the trade being accepted deliberately.

WHY dHash AND NOT A CHECKSUM. A checksum matches the file, and the file is
never what comes back: a re-upload is re-encoded, often rescaled, sometimes
screenshotted. dHash compares the SHAPE of the brightness gradient, so it
survives re-encoding, moderate rescaling and a change of format, which is
exactly the distance between the sticker on disk and the sticker that returns.

WHY THE STICKERS ARE HASHED THREE WAYS. Every one of them carries an alpha
channel. A screenshot has no alpha - the picture has been composited onto
whatever was behind it - so a hash of the raw RGBA matches the file and misses
the screenshot. Each sticker is therefore hashed as it is, and again flattened
onto white and onto the chat's own dark panel. Three cheap hashes per sticker,
computed once and cached.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from django.conf import settings

log = logging.getLogger(__name__)

#: Where the shop's own artwork lives. Both sizes: the full sticker and the
#: picker tile, because the tile is equally copyable off the page.
STICKER_DIRS = (
    os.path.join("images", "chef_battle", "arena", "stickers"),
    os.path.join("images", "chef_battle", "arena", "stickers", "tile"),
)

#: The backgrounds a screenshot could have flattened the alpha onto. Cream is
#: the site's own parchment, the dark one is the chat panel in its dark theme.
FLATTEN_ON = ((255, 255, 255), (250, 246, 240), (31, 44, 37))

#: Hamming distance, out of 64 bits, at or under which two pictures are called
#: the same. Chosen by measurement rather than by folklore - see
#: StickerLikenessThresholdTests, which requires every sticker to match its own
#: re-encoded and rescaled copy well inside this, and requires the 13 stickers
#: to be further apart from EACH OTHER than this, so the check cannot mistake
#: one sticker for another and cannot mistake a photograph for either.
MATCH_WITHIN = 8


def _dhash(image, size: int = 8) -> int:
    """A 64-bit difference hash: is each pixel brighter than the one right of it.

    Deliberately hand-rolled rather than pulled from `imagehash`. It is twelve
    lines, it adds no dependency to a one-core server, and the alternative
    brings NumPy into the upload path for a 9x8 grayscale resize.
    """
    small = image.convert("L").resize((size + 1, size), _resample())
    bits = 0
    pixels = small.load()
    for y in range(size):
        for x in range(size):
            bits = (bits << 1) | (1 if pixels[x, y] > pixels[x + 1, y] else 0)
    return bits


def _resample():
    from PIL import Image

    # LANCZOS under both the old and new Pillow names; Pillow 10 moved them.
    return getattr(Image, "Resampling", Image).LANCZOS


def _flatten(image, background):
    from PIL import Image

    if image.mode not in ("RGBA", "LA", "P"):
        return image
    rgba = image.convert("RGBA")
    plate = Image.new("RGB", rgba.size, background)
    plate.paste(rgba, mask=rgba.split()[3])
    return plate


def _trimmed(image):
    """The picture with a uniform border removed, or None if there was none.

    A SCREENSHOT IS THE STICKER PLUS THE PAGE AROUND IT. Measured while this
    was being written: a sticker flattened onto the cream panel is caught, and
    the same sticker with 8% of background padding around it is NOT - a
    difference hash reads the whole frame, so padding shifts every gradient it
    compares. Trimming the uniform margin puts the two cases back together and
    costs one bounding-box computation.
    """
    from PIL import Image, ImageChops

    flat = image.convert("RGB")
    corner = flat.getpixel((0, 0))
    plate = Image.new("RGB", flat.size, corner)
    box = ImageChops.difference(flat, plate).convert("L").point(
        lambda v: 255 if v > 12 else 0).getbbox()
    if not box:
        return None
    if box == (0, 0, flat.width, flat.height):
        return None
    if (box[2] - box[0]) < 16 or (box[3] - box[1]) < 16:
        return None
    return flat.crop(box)


def hashes_for(image, *, trim: bool = False) -> list[int]:
    """Every hash one picture should be compared by.

    `trim` is set for the INCOMING upload and never for the shop's own files:
    the sticker on disk has no border to remove, and trimming it would only
    invent a variant nothing will ever match.
    """
    out = [_dhash(image)]
    for background in FLATTEN_ON:
        flat = _flatten(image, background)
        if flat is not image:
            out.append(_dhash(flat))
    if trim:
        cropped = _trimmed(image)
        if cropped is not None:
            out.append(_dhash(cropped))
    return out


def distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


@lru_cache(maxsize=1)
def sticker_hashes() -> dict[int, str]:
    """hash -> the sticker file it came from. Built once per process.

    Read from the SOURCE tree rather than from `staticfiles`, so the check
    works in a test run, in development and on a box where collectstatic has
    not run yet. The files are 13 x ~40KB; the whole table is built in well
    under a second and never rebuilt.
    """
    from PIL import Image

    table: dict[int, str] = {}
    for root in getattr(settings, "STATICFILES_DIRS", []) or []:
        for relative in STICKER_DIRS:
            folder = os.path.join(str(root), relative)
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder)):
                if not name.lower().endswith((".webp", ".png")):
                    continue
                path = os.path.join(folder, name)
                try:
                    with Image.open(path) as art:
                        art.load()
                        for value in hashes_for(art):
                            table.setdefault(value, name)
                except Exception:  # a broken file must not break the chat
                    log.warning("sticker hash skipped: %s", path, exc_info=True)
    return table


def looks_like_a_sticker(image) -> str | None:
    """The sticker this upload is a copy of, or None.

    Returns the filename so the refusal can be logged with what it matched -
    a refusal nobody can attribute is a refusal nobody can debug.
    """
    table = sticker_hashes()
    if not table:
        return None
    for value in hashes_for(image, trim=True):
        for known, name in table.items():
            if distance(value, known) <= MATCH_WITHIN:
                return name
    return None
