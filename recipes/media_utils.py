"""Locating the WebP sibling of an uploaded image.

``generate_media_webp`` writes ``photo.webp`` beside ``photo.png`` at identical
pixel dimensions. This module answers one question — is there a sibling, and what
is its URL — for both templates (via ``recipes.templatetags.media_webp``) and
views that build image dictionaries before rendering.

It returns "" whenever it cannot be certain, so a media tree that is half
converted, or a storage backend that cannot answer, serves the original rather
than a broken image.
"""
from __future__ import annotations

from pathlib import PurePosixPath

from django.core.files.storage import default_storage

SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg"}

# The media tree changes only on upload, so one lookup per file per process is
# enough. A twelve-photo gallery must not cost twelve storage hits per request.
_URL_CACHE: dict[str, str] = {}


def webp_url(image_field) -> str:
    """URL of the WebP sibling for an ImageFieldFile, or "" if there is none."""
    name = getattr(image_field, "name", None)
    if not name:
        return ""

    cached = _URL_CACHE.get(name)
    if cached is not None:
        return cached

    path = PurePosixPath(name)
    if path.suffix.lower() not in SOURCE_SUFFIXES:
        _URL_CACHE[name] = ""
        return ""

    sibling = str(path.with_suffix(".webp"))
    try:
        url = default_storage.url(sibling) if default_storage.exists(sibling) else ""
    except (OSError, ValueError, NotImplementedError):
        url = ""

    _URL_CACHE[name] = url
    return url
