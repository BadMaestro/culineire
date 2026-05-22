"""
articles/templatetags/article_filters.py

Safe editorial formatter for article body text.

Converts plain-text article bodies into well-structured HTML.
All user text is HTML-escaped before output — no raw HTML ever passes through.

Authoring conventions:
  ## Heading      → <h2>
  ### Subheading  → <h3>
  > Quote         → <blockquote><p>…</p></blockquote>
  - item          → <ul><li>…</li></ul>
  * item          → <ul><li>…</li></ul>
  First paragraph → <p class="lead">
  Other paras     → <p>

Single newlines within a paragraph block → <br> (backward-compatible
with articles written for Django's built-in |linebreaks filter).

Blank lines separate block-level elements.
"""

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# Precompiled line-level patterns
_RE_H2 = re.compile(r'^##\s+(.+)$')
_RE_H3 = re.compile(r'^###\s+(.+)$')
_RE_BLOCKQUOTE = re.compile(r'^>\s*(.*)')
_RE_LIST_ITEM = re.compile(r'^[-*]\s+(.+)')

# Split on one or more blank lines (blank = optional whitespace only)
_RE_BLOCK_SEP = re.compile(r'\n[ \t]*\n')


def _para(lines, is_lead):
    """Return a <p> element from a list of text lines. Inner \\n → <br>."""
    inner = '<br>\n'.join(escape(ln.strip()) for ln in lines if ln.strip())
    if not inner:
        return None
    tag = 'p class="lead"' if is_lead else 'p'
    close = 'p'
    return f'<{tag}>{inner}</{close}>'


@register.filter(name='editorial_format', is_safe=False)
def editorial_format(value):
    """
    Render plain-text article body as safe editorial HTML.

    Usage in template: {{ article.body|editorial_format }}

    All user input is escaped.  The filter never passes raw HTML through.
    Existing plain-text articles (written for |linebreaks) remain readable.
    """
    if not value:
        return ''

    # Normalise line endings: browsers submit textarea content with CRLF (\r\n).
    # _RE_BLOCK_SEP only matches LF-only blank lines, so CRLF bodies would not be
    # split into blocks and ## headings in the middle would render as raw text.
    value = value.replace('\r\n', '\n').replace('\r', '\n')

    raw_blocks = _RE_BLOCK_SEP.split(value.strip())
    output = []
    first_para = True  # True until the first <p> is emitted

    for raw in raw_blocks:
        block = raw.strip('\n')
        if not block.strip():
            continue

        lines = block.splitlines()
        non_empty = [ln.strip() for ln in lines if ln.strip()]
        if not non_empty:
            continue

        first_line = non_empty[0]

        # ── H2 ────────────────────────────────────────────────────────────────
        m = _RE_H2.match(first_line)
        if m:
            output.append(f'<h2>{escape(m.group(1))}</h2>')
            rest = non_empty[1:]
            if rest:
                p = _para(rest, first_para)
                if p:
                    output.append(p)
                    first_para = False
            continue

        # ── H3 ────────────────────────────────────────────────────────────────
        m = _RE_H3.match(first_line)
        if m:
            output.append(f'<h3>{escape(m.group(1))}</h3>')
            rest = non_empty[1:]
            if rest:
                p = _para(rest, first_para)
                if p:
                    output.append(p)
                    first_para = False
            continue

        # ── Blockquote (every non-empty line starts with >) ───────────────────
        if all(_RE_BLOCKQUOTE.match(ln) for ln in non_empty):
            parts = [_RE_BLOCKQUOTE.match(ln).group(1) for ln in non_empty]
            inner = '<br>\n'.join(escape(p) for p in parts)
            output.append(f'<blockquote><p>{inner}</p></blockquote>')
            continue

        # ── Unordered list (every non-empty line starts with - or *) ──────────
        if all(_RE_LIST_ITEM.match(ln) for ln in non_empty):
            items = '\n'.join(
                f'  <li>{escape(_RE_LIST_ITEM.match(ln).group(1))}</li>'
                for ln in non_empty
            )
            output.append(f'<ul>\n{items}\n</ul>')
            continue

        # ── Regular paragraph ─────────────────────────────────────────────────
        p = _para(lines, first_para)
        if p:
            output.append(p)
            first_para = False

    return mark_safe('\n'.join(output))
