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
from html.parser import HTMLParser

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# Precompiled line-level patterns
_RE_H2 = re.compile(r'^##\s+(.+)$')
_RE_H3 = re.compile(r'^###\s+(.+)$')
_RE_BLOCKQUOTE = re.compile(r'^>\s*(.*)')
_RE_LIST_ITEM = re.compile(r'^[-*]\s+(.+)')
_RE_STRONG = re.compile(r'\*\*(.+?)\*\*')
_RE_EM = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')

# Split on one or more blank lines (blank = optional whitespace only)
_RE_BLOCK_SEP = re.compile(r'\n[ \t]*\n')


def _format_inline(escaped_text):
    """
    Apply tiny safe inline emphasis after escaping user text.
    Raw HTML remains escaped; only controlled strong/em tags are introduced.
    """
    text = str(escaped_text)
    text = _RE_STRONG.sub(r'<strong>\1</strong>', text)
    return _RE_EM.sub(r'<em>\1</em>', text)


def _para(lines, is_lead):
    """Return a <p> element from a list of text lines. Inner \\n → <br>."""
    inner = '<br>\n'.join(_format_inline(escape(ln.strip())) for ln in lines if ln.strip())
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
            output.append(f'<h2>{_format_inline(escape(m.group(1)))}</h2>')
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
            output.append(f'<h3>{_format_inline(escape(m.group(1)))}</h3>')
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
            inner = '<br>\n'.join(_format_inline(escape(p)) for p in parts)
            output.append(f'<blockquote><p>{inner}</p></blockquote>')
            continue

        # ── Unordered list (every non-empty line starts with - or *) ──────────
        if all(_RE_LIST_ITEM.match(ln) for ln in non_empty):
            items = '\n'.join(
                f'  <li>{_format_inline(escape(_RE_LIST_ITEM.match(ln).group(1)))}</li>'
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


class _RecipeLinker(HTMLParser):
    def __init__(self, recipe_terms, max_links=3):
        super().__init__(convert_charrefs=False)
        self.recipe_terms = recipe_terms
        self.max_links = max_links
        self.link_count = 0
        self.linked_terms = set()
        self.skip_stack = []
        self.output = []

    def _in_skip_context(self):
        return bool(self.skip_stack)

    def handle_starttag(self, tag, attrs):
        if tag in {"a", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.skip_stack.append(tag)
        attr_text = "".join(f' {name}="{escape(value or "")}"' for name, value in attrs)
        self.output.append(f"<{tag}{attr_text}>")

    def handle_endtag(self, tag):
        self.output.append(f"</{tag}>")
        if self.skip_stack and self.skip_stack[-1] == tag:
            self.skip_stack.pop()

    def handle_startendtag(self, tag, attrs):
        attr_text = "".join(f' {name}="{escape(value or "")}"' for name, value in attrs)
        self.output.append(f"<{tag}{attr_text}>")

    def handle_entityref(self, name):
        self.output.append(f"&{name};")

    def handle_charref(self, name):
        self.output.append(f"&#{name};")

    def handle_data(self, data):
        if self._in_skip_context() or self.link_count >= self.max_links:
            self.output.append(data)
            return

        updated = data
        for label, url in self.recipe_terms:
            if self.link_count >= self.max_links:
                break
            key = label.lower()
            if key in self.linked_terms:
                continue
            pattern = re.compile(rf'(?<![\w-])({re.escape(label)})(?![\w-])', re.IGNORECASE)
            if not pattern.search(updated):
                continue
            updated = pattern.sub(
                rf'<a class="editorial-link" href="{escape(url)}">\1</a>',
                updated,
                count=1,
            )
            self.linked_terms.add(key)
            self.link_count += 1

        self.output.append(updated)


def add_internal_recipe_links(html, recipes, max_links=3):
    """
    Link first mentions of approved recipe titles in already-safe editorial HTML.
    Headings and existing links are left untouched.
    """
    recipe_terms = []
    for recipe in recipes or []:
        title = (getattr(recipe, "title", "") or "").strip()
        if len(title) < 4:
            continue
        recipe_terms.append((title, recipe.get_absolute_url()))

    if not recipe_terms:
        return mark_safe(html or "")

    recipe_terms.sort(key=lambda item: len(item[0]), reverse=True)
    parser = _RecipeLinker(recipe_terms, max_links=max_links)
    parser.feed(str(html or ""))
    parser.close()
    return mark_safe("".join(parser.output))
