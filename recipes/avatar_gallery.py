"""The gallery of ready-made portraits a person may pick for himself.

The Owner, 2026-08-17. The site owns 96 generated portraits, and the question
was whether an author who uploads no photograph could be GIVEN one of them
automatically, chosen from the gender he selected at registration. His ruling
stopped that, and the reason is the important part:

    they are realistic and carry racial features, skin colours and so on -- we
    have no right to assign them by default

Assigning a photorealistic face to a real person attributes an appearance,
an ethnicity and an age that person never claimed. So nothing here is ever
applied automatically. The gallery exists only behind a "More" link on the
registration form: the person opens it, looks, and picks one himself. A picture
he chose is his; a picture we chose for him is us speaking on his behalf.

The three illustrated stand-ins stay exactly as they were and remain the
default. This only adds a wider choice for someone who wants one.
"""

from __future__ import annotations

from django.templatetags.static import static

# static/images/crowd/face-01.webp .. face-96.webp. Named rather than globbed so
# the set a form will accept cannot change because of what happens to be on disk
# on one machine.
GALLERY_COUNT = 96
GALLERY_KEYS = tuple(f"face-{index:02d}" for index in range(1, GALLERY_COUNT + 1))
GALLERY_KEY_SET = frozenset(GALLERY_KEYS)


def is_gallery_key(value: str) -> bool:
    return bool(value) and value in GALLERY_KEY_SET


def gallery_url(key: str) -> str:
    """Static URL for a gallery key, or an empty string if it is not one.

    Returning "" rather than raising keeps a stale value in an old row from
    turning a profile page into a 500: the caller falls back to the
    illustration it would have used anyway.
    """
    if not is_gallery_key(key):
        return ""
    return static(f"images/crowd/{key}.webp")


def gallery_choices() -> list[tuple[str, str]]:
    """(key, url) pairs for the picker, in file order."""
    return [(key, gallery_url(key)) for key in GALLERY_KEYS]
