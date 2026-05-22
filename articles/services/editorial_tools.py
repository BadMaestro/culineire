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
# Theme table for content-aware section grouping.
# Each paragraph is scored against every theme by counting keyword hits in the
# lowercased paragraph text.  The theme with the highest count wins; the first
# theme in this list wins on a tie.
#
# Headings are inserted in the order paragraphs appear in the article —
# not the order entries appear here.  List order affects only tie-breaking.
_SECTION_THEMES = [
    {
        "name": "familiar_icons",
        "keywords": ["butter", "cream", "stout", "whiskey", "whisky", "dairy"],
        "heading": "Irish Food Beyond the Familiar Icons",
    },
    {
        "name": "land_and_rural",
        "keywords": ["land", "season", "seasonal", "rural", "countryside", "farm", "farming", "harvest", "local"],
        "heading": "Food Rooted in the Land",
    },
    {
        "name": "history",
        "keywords": ["history", "century", "centuries", "ancient", "medieval", "heritage", "generation", "generations", "tradition"],
        "heading": "A Heritage Built Through Generations",
    },
    {
        "name": "baking",
        "keywords": ["baking", "bread", "oats", "griddle", "soda", "loaf", "farls", "bannocks"],
        "heading": "Baking, Griddles and the Country Kitchen",
    },
    {
        "name": "simple_ingredients",
        "keywords": ["potato", "potatoes", "oats", "grain", "grains", "dairy", "herbs", "vegetables"],
        "heading": "Simple Ingredients, Lasting Identity",
    },
    {
        "name": "mills",
        "keywords": ["mill", "mills", "milling", "grain", "flour", "watermills", "windmills"],
        "heading": "Mills, Grain and Rural Memory",
    },
    {
        "name": "modern",
        "keywords": ["revival", "modern", "restaurant", "bistro", "chef", "contemporary", "dublin", "belfast"],
        "heading": "A Living Culinary Heritage",
    },
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
# Plain paragraphs longer than this word count are split at a sentence boundary.
_PARA_SPLIT_THRESHOLD = 130

_RE_BLOCK_SEP = re.compile(r"\n[ \t]*\n")
_RE_H2 = re.compile(r"^##\s+")
_RE_BULLET = re.compile(r"^[-*]\s+")
# Splits after sentence-ending punctuation followed by whitespace + a capital letter.
_RE_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# Recipe-specific patterns
_RE_BLANK_LINE = re.compile(r'[ \t]*\n[ \t]*\n')
_RE_STEP_PREFIX = re.compile(r'^\s*(?:step\s*)?\d+[\.\):\-]?\s*', re.IGNORECASE)


# ── Article tools ─────────────────────────────────────────────────────────────

def suggest_article_body(title: str, excerpt: str, body: str) -> str:
    """
    Return a suggested reformatted body string (deterministic, no AI).

    Algorithm
    ---------
    1. Normalise whitespace; return unchanged if body already has ## headings.
    2. Return unchanged if body is short (< 300 words).
    3. Split body into paragraph blocks; split any plain paragraph over
       _PARA_SPLIT_THRESHOLD words at a sentence boundary (no rewrites).
    4. Keep the first 1 or 2 plain paragraphs as a lead section — no heading
       appears above them.
    5. Classify each remaining plain paragraph against _SECTION_THEMES by
       counting keyword matches.  The theme with the highest count wins;
       the first theme in _SECTION_THEMES breaks ties.
    6. Group consecutive paragraphs that share the same best theme.
    7. If there are more groups than max_headings, repeatedly merge the two
       adjacent groups with the smallest combined paragraph count
       (earlier pair wins on tie) until within budget.
    8. Assign each group its theme heading, or the first unused fallback when
       no theme matched.  Headings are emitted in paragraph order —
       not dictionary order.
    9. List and blockquote blocks never receive an injected heading.

    Heading count ceiling
    ---------------------
    < 600 words  → 4   |   < 900 words  → 5
    < 1200 words → 6   |   otherwise    → 7

    Rules
    -----
    - Never outputs "Introduction", "Background" or other academic headings.
    - Original wording is never changed.
    """
    if not body or not body.strip():
        return body or ""

    cleaned = _normalize_body(body)

    if _has_h2(cleaned):
        return cleaned

    word_count = len(cleaned.split())
    if word_count < _MIN_WORDS_FOR_HEADING_INSERTION:
        return cleaned

    # Max headings scaled to article length
    if word_count < 600:
        max_headings = 4
    elif word_count < 900:
        max_headings = 5
    elif word_count < 1200:
        max_headings = 6
    else:
        max_headings = 7

    # Lead count: two paragraphs for longer articles, one for shorter
    lead_count = 2 if word_count >= 400 else 1

    # Split into blocks; expand any overlong plain paragraph
    raw_blocks = [b.strip() for b in _RE_BLOCK_SEP.split(cleaned) if b.strip()]
    blocks = _split_long_blocks(raw_blocks)

    # Identify plain block indices (not headings, not lists)
    plain_indices = []
    for i, block in enumerate(blocks):
        fl = block.splitlines()[0] if block else ""
        if not fl.startswith("#") and not _RE_BULLET.match(fl):
            plain_indices.append(i)

    # Post-lead plain indices
    post_lead = plain_indices[lead_count:]

    if not post_lead:
        return "\n\n".join(blocks)

    # Score each post-lead plain block against all themes
    scored = [
        (idx, _score_para_theme(blocks[idx].lower()))
        for idx in post_lead
    ]

    # Build theme groups: consecutive blocks sharing the same best theme.
    # Each entry: [theme_name_or_None, [block_indices], theme_dict_or_None]
    groups = []
    for block_idx, theme in scored:
        theme_name = theme["name"] if theme else None
        if groups and groups[-1][0] == theme_name:
            groups[-1][1].append(block_idx)
        else:
            groups.append([theme_name, [block_idx], theme])

    # Reduce groups to max_headings by merging the two adjacent groups
    # with the smallest combined size (earlier pair wins on tie).
    while len(groups) > max_headings:
        merge_at = 0
        min_size = len(groups[0][1]) + len(groups[1][1])
        for i in range(1, len(groups) - 1):
            combined = len(groups[i][1]) + len(groups[i + 1][1])
            if combined < min_size:
                min_size = combined
                merge_at = i
        # Keep the first group's theme (preserves article order priority)
        merged_name = (
            groups[merge_at][0]
            if groups[merge_at][0] is not None
            else groups[merge_at + 1][0]
        )
        merged_obj = (
            groups[merge_at][2]
            if groups[merge_at][2] is not None
            else groups[merge_at + 1][2]
        )
        merged_indices = groups[merge_at][1] + groups[merge_at + 1][1]
        groups[merge_at : merge_at + 2] = [[merged_name, merged_indices, merged_obj]]

    # Assign headings — processed in group order = paragraph/article order.
    used_headings: set = set()
    heading_before: dict = {}  # block_index → heading text

    for theme_name, indices, theme_obj in groups:
        if theme_obj is not None and theme_obj["heading"] not in used_headings:
            h = theme_obj["heading"]
        else:
            h = next(
                (fb for fb in _FALLBACK_HEADINGS if fb not in used_headings),
                "Irish Food Heritage",
            )
        used_headings.add(h)
        heading_before[min(indices)] = h

    # Assemble final output
    result_blocks = []
    for i, block in enumerate(blocks):
        if i in heading_before:
            result_blocks.append("## " + heading_before[i])
        result_blocks.append(block)

    return "\n\n".join(result_blocks)


def _score_para_theme(text_lower: str):
    """
    Return the best-matching theme dict from _SECTION_THEMES, or None if no
    theme has any keyword match.  First theme in the list wins on equal scores.
    """
    best_theme = None
    best_score = 0
    for theme in _SECTION_THEMES:
        score = sum(1 for kw in theme["keywords"] if kw in text_lower)
        if score > best_score:
            best_score = score
            best_theme = theme
    return best_theme  # None when best_score == 0


def _split_long_blocks(blocks: list, threshold: int = _PARA_SPLIT_THRESHOLD) -> list:
    """
    Split plain paragraph blocks that exceed `threshold` words at a sentence
    boundary near the midpoint.  Never modifies wording.
    Heading and list blocks pass through unchanged.
    """
    result = []
    for block in blocks:
        fl = block.splitlines()[0] if block else ""
        if fl.startswith("#") or _RE_BULLET.match(fl) or len(block.split()) <= threshold:
            result.append(block)
            continue
        sentences = _RE_SENTENCE_END.split(block)
        if len(sentences) < 2:
            result.append(block)
            continue
        target = len(block.split()) // 2
        words_so_far = 0
        split_at = len(sentences) - 1  # fallback: split before last sentence
        for idx, sent in enumerate(sentences[:-1]):
            words_so_far += len(sent.split())
            if words_so_far >= target:
                split_at = idx + 1
                break
        first_half = " ".join(sentences[:split_at]).strip()
        second_half = " ".join(sentences[split_at:]).strip()
        if first_half and second_half:
            result.extend([first_half, second_half])
        else:
            result.append(block)
    return result


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
