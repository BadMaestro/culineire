from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def executive_badge(author):
    """Render Executive Chef badge if the author is the site owner."""
    if author and getattr(author, "is_owner", False):
        return format_html('<span class="badge-executive">Executive Chef</span>')
    return ""
