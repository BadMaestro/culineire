"""A WebP sibling for an uploaded image, when one has been generated.

Uploaded photographs are the heaviest thing this site serves. Measured on
production, 2026-07-26, on a public recipe page: 4,198 KB of images, of which
3,951 KB came from /media/ — a single gallery PNG was 2,291 KB while rendering at
473x378. Nothing was watching, because the weight guard scans ``static`` and this
lives in ``media``.

The fix keeps every original byte on disk. ``generate_media_webp`` writes a
``.webp`` beside each uploaded image, and this filter hands the template that
sibling's URL so it can be offered as a ``<picture><source>``. If the sibling has
not been generated, the filter returns an empty string and the template falls
back to the original — so a half-generated media tree is never a broken page.
"""
from __future__ import annotations

from pathlib import PurePosixPath

from django import template
from django.core.files.storage import default_storage

register = template.Library()

SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg"}

# One process serves many pages; the media tree changes only when someone
# uploads. Remember what exists so a gallery of twelve photographs costs twelve
# storage lookups once, not on every request.
_EXISTS_CACHE: dict[str, str] = {}


@register.filter
def webp(image_field) -> str:
    """Return the URL of the WebP sibling, or "" when there is not one."""
    name = getattr(image_field, "name", None)
    if not name:
        return ""

    cached = _EXISTS_CACHE.get(name)
    if cached is not None:
        return cached

    path = PurePosixPath(name)
    if path.suffix.lower() not in SOURCE_SUFFIXES:
        _EXISTS_CACHE[name] = ""
        return ""

    sibling = str(path.with_suffix(".webp"))
    try:
        url = default_storage.url(sibling) if default_storage.exists(sibling) else ""
    except (OSError, ValueError, NotImplementedError):
        # A storage backend that cannot answer is not a reason to break a page.
        url = ""

    _EXISTS_CACHE[name] = url
    return url
