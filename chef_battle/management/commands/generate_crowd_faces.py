"""Generate the stand-in crowd that fills empty seats in the arena stands.

The stands hold 544 seats and the site has three default avatars, so before
this the same three faces repeated across the hall in a visible diagonal —
the owner's words were that they sit like eggs in a carton. This draws a set
of distinct portraits instead, on a transparent background so nothing but the
face lands in the seat.

Uses the same OpenAI image endpoint as recipes/management/commands/
generate_recipe.py, with two extra parameters that helper does not send:
background=transparent and output_format=png, which is what lets the seat
show the hall behind the head rather than a grey box.

    python manage.py generate_crowd_faces          # only what is missing
    python manage.py generate_crowd_faces --force  # redraw everything
"""
import base64
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# A hall in Cork, not a stock-photo set. Each entry varies age, build,
# colouring and dress, because what makes a crowd read as a crowd is that no
# two people beside each other are the same person. Kept deliberately plain:
# these sit 6-20px wide, so anything smaller than hair, skin and a collar is
# detail nobody will ever see.
FACES = [
    "an older man with a white beard and ruddy cheeks, flat cap",
    "a young woman with dark curly hair, hoop earrings",
    "a middle-aged black man with short grey-flecked hair, open collar",
    "a red-haired freckled woman in her thirties, hair tied back",
    "an elderly woman with silver hair and glasses, warm smile",
    "a young south-asian man with black hair and a trimmed beard",
    "a blonde woman in her forties, shoulder-length hair",
    "a bald man in his fifties with a heavy build, checked shirt",
    "a teenage girl with a dark ponytail and a hoodie",
    "an east-asian woman in her twenties with straight black hair",
    "a bearded man in his thirties with a beanie hat",
    "a woman in her sixties with short grey hair and a scarf",
]

PROMPT = (
    "Head-and-shoulders portrait photograph of {subject}. "
    "Facing the camera, neutral friendly expression, eyes in the upper third of the frame. "
    "Warm indoor lighting from above, as if seated in the audience of a lit hall. "
    "Isolated subject on a fully transparent background, no scenery, no chair, no border, "
    "nothing behind the head. Photographic, not illustrated. Head fills most of the frame."
)


# Cheapest tier, deliberately NOT settings.OPENAI_IMAGE_QUALITY. That setting
# is "medium" on production because a recipe's hero photo is looked at; these
# are drawn 6-20px wide in the stands, where the difference between quality
# tiers is invisible and the difference in the bill is not. Overridable with
# --quality if a face ever needs to be looked at closely.
DEFAULT_QUALITY = "low"


def fetch_transparent_png(prompt: str, quality: str) -> bytes:
    """OpenAI image generation, forced to a transparent-background PNG."""
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise CommandError("OPENAI_API_KEY is not configured.")
    payload = {
        "model": getattr(settings, "OPENAI_IMAGE_MODEL", "gpt-image-1"),
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "quality": quality,
        "background": "transparent",
        "output_format": "png",
    }
    req = Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=180) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise CommandError(f"OpenAI returned HTTP {exc.code}: {exc.read().decode('utf-8')[:300]}") from exc
    except (URLError, OSError) as exc:
        raise CommandError(f"OpenAI image request failed: {exc}") from exc

    try:
        entry = json.loads(body)["data"][0]
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        raise CommandError(f"Unexpected response: {exc} — {body[:200]}") from exc
    if "b64_json" not in entry:
        raise CommandError("Response carried no b64_json; transparent output expects inline data.")
    return base64.b64decode(entry["b64_json"])


def to_seat_size(raw: bytes, size: int) -> bytes:
    """Trim to what is actually drawn, square it up, and save at seat size."""
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    # The model leaves a wide transparent margin; the face is what remains.
    bbox = img.getchannel("A").getbbox()
    if bbox:
        img = img.crop(bbox)
    # Square around the centre of the head so the circular clip in
    # arena_render.js cuts a face, not an ear.
    side = max(img.width, img.height)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    square = square.resize((size, size), Image.LANCZOS)

    buf = io.BytesIO()
    square.save(buf, format="WEBP", quality=88, method=6)
    return buf.getvalue()


class Command(BaseCommand):
    help = "Draw the arena's stand-in crowd portraits (transparent background)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", default=False,
                            help="Redraw faces that already exist.")
        parser.add_argument("--size", type=int, default=96,
                            help="Output edge in pixels (default 96).")
        parser.add_argument("--limit", type=int, default=0,
                            help="Draw at most this many (0 = all).")
        parser.add_argument("--quality", choices=["low", "medium", "high"],
                            default=DEFAULT_QUALITY,
                            help="Image quality tier (default low — these are drawn tiny).")
        parser.add_argument("--out", default="",
                            help="Write here instead of static/images/crowd. On the "
                                 "server that directory belongs to root while this "
                                 "command runs as deploy, so draw to a scratch path "
                                 "and commit the files rather than chowning the tree.")

    def handle(self, *args, **options):
        dest_dir = Path(options["out"]) if options["out"] else (
            Path(settings.BASE_DIR) / "static" / "images" / "crowd"
        )
        dest_dir.mkdir(parents=True, exist_ok=True)

        subjects = FACES[: options["limit"]] if options["limit"] else FACES
        quality = options["quality"]
        drawn = 0

        self.stdout.write(
            f"model {getattr(settings, 'OPENAI_IMAGE_MODEL', 'gpt-image-1')}, "
            f"quality {quality}, size 1024x1024, {len(subjects)} face(s)"
        )

        for index, subject in enumerate(subjects, start=1):
            dest = dest_dir / f"face-{index:02d}.webp"
            if dest.exists() and not options["force"]:
                self.stdout.write(self.style.WARNING(f"  skip  {dest.name}"))
                continue

            self.stdout.write(f"  draw  {dest.name} — {subject} …", ending="")
            self.stdout.flush()
            raw = fetch_transparent_png(PROMPT.format(subject=subject), quality)
            dest.write_bytes(to_seat_size(raw, options["size"]))
            drawn += 1
            self.stdout.write(self.style.SUCCESS(f" {dest.stat().st_size} bytes"))

        self.stdout.write(self.style.SUCCESS(f"\nDrawn {drawn} of {len(subjects)}."))

