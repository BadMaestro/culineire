"""Template access to the WebP sibling of an uploaded image.

The logic lives in ``recipes.media_utils`` so views can use it too when they
build image dictionaries before rendering. See that module for why uploaded
photographs needed this at all.
"""
from __future__ import annotations

from django import template

from recipes.media_utils import webp_url

register = template.Library()


@register.filter
def webp(image_field) -> str:
    """Return the URL of the WebP sibling, or "" when there is not one."""
    return webp_url(image_field)
