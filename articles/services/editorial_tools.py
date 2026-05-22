"""
articles/services/editorial_tools.py

Deterministic editorial automation helpers.  No AI, no external API,
no database writes.  All functions are pure or read-only.

Article tools
-------------
  suggest_article_body(title, excerpt, body) -> str
  render_article_preview(body)               -> SafeString

Recipe tools
------------
  suggest_recipe_fields(data) -> dict
  render_recipe_preview(data) -> SafeString
"""

import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

# ── Article heading tables ─────────────────────────────────────────────────────
#
# Contextual headings: (keyword_list, heading_text).
# Matched against the full lowercased body text.  First match wins for each slot.
# Order matters — more specific / distinctive Irish themes first.
_CONTEXTUAL_HEADINGS = [
    (
        ["potato", "colcannon", "boxty", "champ", "spud"],
        "The Potato and Its Place",
    ),
    (
        ["butter", "cream", "stout", "whiskey", "whisky", "guinness"],
        "Irish Food Beyond the Familiar Icons",
    ),
    (
        ["baking", "bread", "oats", "griddle", "soda", "loaf", "scone"],
        "Baking, Griddles and the Country Kitchen",
    ),
    (
        ["mill", "grain", "flour", "milling"],
        "Mills, Grain and Rural Memory",
    ),
    (
        ["fishing", "fish", "seafood", "coast", "coastal", "atlantic", "harbour"],
        "Coastal Traditions and the Sea",
    ),
    (
        ["land", "season", "seasonal", "rural", "countryside", "farm", "harvest"],
        "Food Rooted in the Land",
    ),
    (
        ["revival", "modern", "restaurant", "bistro", "chef", "contemporary"],
        "A Living Culinary Heritage",
    ),
    (
        ["history", "century", "centuries", "ancient", "medieval", "historical"],
        "Rooted in History",
    ),
]

# Soft editorial fallbacks used when keyword matching is exhausted.
# None of these should sound like a school report.
_FALLBACK_HEADINGS = [
    "Food Rooted in Place",
    "A Tradition Built on Simple Ingredients",
    "The Country Kitchen",
    "From Everyday Cooking to Heritage",
    "Why It Still Matters",
]

_MIN_WORDS_FOR_HEADING_INSERTION = 300
# First N plain paragraphs remain as a lead section before any heading is inserted.
_LEAD_PARAGRAPHS = 1

_RE_BLOCK_SEP = re.compile(r'\n[ \t]*\n')
_RE_H2 = re.compile(r'^##\s+')
_RE_BULLET = re.compile(r'^[-*]\s+')

# Recipe-specific patterns
_RE_BLANK_LINE = re.compile(r'[ \t]*\n[ \t]*\n')
_RE_STEP_PREFIX = re.compile(r'^\s*(?:step\s*)?\d+[\.\):\-]?\s*', re.IGNORECASE)


# ── Article tools ─────────────────────────────────────────────────────────────

def suggest_article_body(title: str, excerpt: str, body: str) -> str:
    """
    Return a suggested reformatted body string (deterministic, no AI).

    Rules
    -----
    - Body already has ## headings → return normalised body unchanged.
    - Body is short (< 300 words) → return normalised body unchanged.
    - Otherwise:
        * Keep the first paragraph(s) as a lead section (no heading before them).
        * Insert editorial headings chosen from the contextual / fallback tables,
          once every two plain-paragraph blocks after the lead.
        * Maximum headings: 2 for <500 words, 3 for <800 words,
          4 for <1200 words, 5 for longer articles.
        * Never output "Introduction", "Background" or other academic headings.
        * List and blockquote blocks are never preceded by an inserted heading.
    """
    if not body or not body.strip():
        return body or ""

    cleaned = _normalize_body(body)

    if _has_h2(cleaned):
        return cleaned

    word_count = len(cleaned.split())
    if word_count < _MIN_WORDS_FOR_HEADING_INSERTION:
        return cleaned

    # Scale heading density to article length
    if word_count < 500:
        max_headings = 2
    elif word_count < 800:
        max_headings = 3
    elif word_count < 1200:
        max_headings = 4
    else:
        max_headings = 5

    heading_pool = _build_heading_pool(cleaned.lower(), max_headings)
    blocks = [b.strip() for b in _RE_BLOCK_SEP.split(cleaned) if b.strip()]

    result_blocks = []
    para_count = 0   # counts plain-paragraph blocks seen so far
    heading_index = 0

    for block in blocks:
        first_line = block.splitlines()[0] if block else ""
        is_heading = first_line.startswith("#")
        is_list = bool(_RE_BULLET.match(first_line))
        is_plain = not is_heading and not is_list

        if is_plain:
            # Skip the lead paragraphs; after that insert a heading every 2nd block.
            if (
                para_count >= _LEAD_PARAGRAPHS
                and heading_index < len(heading_pool)
                and (para_count - _LEAD_PARAGRAPHS) % 2 == 0
            ):
                result_blocks.append("## " + heading_pool[heading_index])
                heading_index += 1
            para_count += 1

        result_blocks.append(block)

    return "\n\n".join(result_blocks)


def _build_heading_pool(body_lower: str, max_count: int) -> list:
    """
    Return up to max_count editorial headings for the given body text.

    Scans body_lower for keyword matches (contextual headings first),
    then fills remaining slots from the soft fallback list.
    No heading appears more than once.
    """
    pool = []
    seen = set()

    for keywords, heading in _CONTEXTUAL_HEADINGS:
        if len(pool) >= max_count:
            break
        if heading not in seen and any(kw in body_lower for kw in keywords):
            pool.append(heading)
            seen.add(heading)

    for heading in _FALLBACK_HEADINGS:
        if len(pool) >= max_count:
            break
        if heading not in seen:
            pool.append(heading)
            seen.add(heading)

    return pool[:max_count]


def render_article_preview(body: str) -> str:
    """
    Return safe HTML preview of an article body using the editorial_format filter.
    """
    from articles.templatetags.article_filters import editorial_format
    return editorial_format(body or "")


def _normalize_body(body: str) -> str:
    """Strip trailing whitespace per line; collapse runs of blank lines to one."""
    lines = [ln.rstrip() for ln in body.splitlines()]
    result = []
    blank_run = 0
    for ln in lines:
        if not ln.strip():
            blank_run += 1
            if blank_run <= 1:
                result.append("")
        else:
            blank_run = 0
            result.append(ln)
    return "\n".join(result).strip()


def _has_h2(body: str) -> bool:
    return any(_RE_H2.match(ln) for ln in body.splitlines())


# ── Recipe tools ──────────────────────────────────────────────────────────────

def suggest_recipe_fields(data: dict) -> dict:
    """
    Return a normalised copy of recipe text fields (no DB write).

    Normalisation rules:
    - ingredients : one item per line, strip blank lines, strip leading
                    bullet/dash/bullet characters.
    - method      : one step per line, strip blank lines, strip leading
                    step-number prefixes ("1. ", "Step 2:", "2)").
    - tips        : strip blank lines, collapse trailing whitespace.
    - irish_context / author_commentary : strip trailing whitespace per line.

    All other keys returned unchanged.
    """
    result = dict(data)

    if "ingredients" in data:
        result["ingredients"] = _clean_list_field(data["ingredients"])

    if "method" in data:
        result["method"] = _clean_method_field(data["method"])

    for key in ("tips", "irish_context", "author_commentary"):
        if key in data:
            result[key] = _clean_plain_field(data[key])

    return result


def render_recipe_preview(data: dict) -> str:
    """
    Return safe HTML preview of recipe fields.
    All user content is escaped; output is marked safe.
    """
    parts = []

    title = (data.get("title") or "").strip()
    if title:
        parts.append('<h2 class="recipe-preview__title">' + escape(title) + "</h2>")

    desc = (data.get("short_description") or "").strip()
    if desc:
        parts.append('<p class="recipe-preview__desc">' + escape(desc) + "</p>")

    meta_items = []
    for key, label in [
        ("prep_time_minutes", "Prep"),
        ("cook_time_minutes", "Cook"),
        ("servings", "Serves"),
        ("difficulty", "Difficulty"),
    ]:
        val = str(data.get(key) or "").strip()
        if val:
            meta_items.append(
                "<span><strong>" + escape(label) + ":</strong> " + escape(val) + "</span>"
            )
    if meta_items:
        parts.append(
            '<div class="recipe-preview__meta">'
            + "&ensp;|&ensp;".join(meta_items)
            + "</div>"
        )

    ingredients = (data.get("ingredients") or "").strip()
    if ingredients:
        items = [ln.strip() for ln in ingredients.splitlines() if ln.strip()]
        li_html = "\n".join("  <li>" + escape(item) + "</li>" for item in items)
        parts.append(
            '<div class="recipe-preview__section">'
            '<p class="recipe-preview__section-title">Ingredients</p>'
            '<ul class="recipe-preview__list">\n' + li_html + "\n</ul>"
            "</div>"
        )

    method = (data.get("method") or "").strip()
    if method:
        steps = [ln.strip() for ln in method.splitlines() if ln.strip()]
        li_html = "\n".join(
            '  <li><span class="recipe-preview__step-num">'
            + str(i)
            + ".</span> "
            + escape(step)
            + "</li>"
            for i, step in enumerate(steps, 1)
        )
        parts.append(
            '<div class="recipe-preview__section">'
            '<p class="recipe-preview__section-title">Method</p>'
            '<ol class="recipe-preview__steps">\n' + li_html + "\n</ol>"
            "</div>"
        )

    tips = (data.get("tips") or "").strip()
    if tips:
        parts.append(
            '<div class="recipe-preview__section">'
            '<p class="recipe-preview__section-title">Tips</p>'
            '<p class="recipe-preview__tips">' + escape(tips) + "</p>"
            "</div>"
        )

    if not parts:
        return mark_safe('<p class="recipe-preview__empty">Nothing to preview yet.</p>')

    return mark_safe("\n".join(parts))


def _clean_list_field(text: str) -> str:
    """Normalise an ingredients-style list: one item per line, no leading bullets."""
    if not text:
        return text or ""
    cleaned = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln and ln[0] in "-*•":
            ln = ln[1:].strip()
        if ln:
            cleaned.append(ln)
    return "\n".join(cleaned)


def _clean_method_field(text: str) -> str:
    """Normalise a method: one step per line, strip step-number prefixes."""
    if not text:
        return text or ""
    raw_blocks = _RE_BLANK_LINE.split(text)
    lines = []
    for block in raw_blocks:
        for ln in block.splitlines():
            ln = ln.strip()
            if ln:
                lines.append(ln)
    cleaned = []
    for ln in lines:
        ln = _RE_STEP_PREFIX.sub("", ln).strip()
        if ln:
            cleaned.append(ln)
    return "\n".join(cleaned)


def _clean_plain_field(text: str) -> str:
    """Strip trailing whitespace per line; collapse consecutive blank lines to one."""
    if not text:
        return text or ""
    lines = [ln.rstrip() for ln in text.splitlines()]
    result = []
    blank_run = 0
    for ln in lines:
        if not ln.strip():
            blank_run += 1
            if blank_run <= 1:
                result.append("")
        else:
            blank_run = 0
            result.append(ln)
    return "\n".join(result).strip()
