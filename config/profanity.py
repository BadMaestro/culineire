"""
Profanity / forbidden-word filter for CulinEire.

Words are managed via the Monitoring Dashboard (/monitoring/profanity/).
The database is the authoritative source; this module caches the compiled
regex for _CACHE_TTL seconds to avoid rebuilding it on every form submission.

Usage
-----
    from config.profanity import find_profanity, contains_profanity

    words = find_profanity("some text")    # -> list[str] of matched words (lowercase)
    ok    = not contains_profanity(text)   # -> bool

To force a cache refresh after adding/deleting words call:
    from config.profanity import invalidate_profanity_cache
    invalidate_profanity_cache()
"""

import logging
import re
import threading
import time as _time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in fallback list (used when the DB is unavailable, e.g. during tests
# or before the first migration).  Keep in sync with the seeding list in
# monitoring/migrations/0003_add_profanity_word.py.
# ---------------------------------------------------------------------------

_BUILTIN_WORDS: list[str] = [
    # ── Core English profanity ──────────────────────────────────────────────
    "fuck", "fucked", "fucker", "fucking", "fucks", "fuckin",
    "motherfucker", "motherfucking",
    "cunt", "cunts",
    "shit", "shits", "shitty", "shitting", "bullshit", "shite",
    "bitch", "bitches",
    "bastard", "bastards",
    "asshole", "assholes", "arsehole", "arseholes",
    "dickhead", "dickheads",
    "prick", "pricks",
    "wanker", "wankers", "wank", "wanking",
    "twat", "twats",
    "bollocks",
    "whore", "whores",
    "slut", "sluts",

    # ── Racial / ethnic slurs ───────────────────────────────────────────────
    "nigger", "niggers", "nigga", "niggas",
    "kike", "kikes",
    "chink", "chinks",
    "spic", "spics",
    "gook", "gooks",
    "wetback", "wetbacks",
    "raghead", "ragheads",
    "towelhead",
    "zipperhead",

    # ── Homophobic / transphobic slurs ─────────────────────────────────────
    "faggot", "faggots",
    "tranny", "trannies",

    # ── Ableist slurs ───────────────────────────────────────────────────────
    "retard", "retarded", "retards",
    "spastic",
]

# ---------------------------------------------------------------------------
# In-process cache
# ---------------------------------------------------------------------------

_CACHE_TTL: float = 60.0

_lock = threading.Lock()
_cached_words: list[str] | None = None
_cached_pattern: re.Pattern | None = None
_cache_ts: float = 0.0


def _load_words() -> list[str]:
    try:
        from monitoring.models import ProfanityWord
        words = list(ProfanityWord.objects.values_list("word", flat=True))
        return words if words else _BUILTIN_WORDS
    except Exception:
        logger.warning("Profanity word list could not be loaded from DB, using built-in fallback", exc_info=True)
        return _BUILTIN_WORDS


def _get_pattern() -> re.Pattern:
    global _cached_words, _cached_pattern, _cache_ts

    now = _time.monotonic()
    if _cached_pattern is not None and (now - _cache_ts) < _CACHE_TTL:
        return _cached_pattern

    with _lock:
        if _cached_pattern is not None and (now - _cache_ts) < _CACHE_TTL:
            return _cached_pattern
        words = _load_words()
        _cached_words = words
        _cached_pattern = re.compile(
            r"\b(" + "|".join(re.escape(w) for w in words) + r")\b",
            re.IGNORECASE,
        )
        _cache_ts = now
    return _cached_pattern


def invalidate_profanity_cache() -> None:
    global _cached_words, _cached_pattern, _cache_ts
    with _lock:
        _cached_words = None
        _cached_pattern = None
        _cache_ts = 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_profanity(text: str) -> list[str]:
    """Return a sorted list of unique forbidden words found in *text* (lowercase)."""
    if not text:
        return []
    if not isinstance(text, str):
        return []
    pattern = _get_pattern()
    return sorted({m.group(0).lower() for m in pattern.finditer(text)})


def contains_profanity(text: str) -> bool:
    """Return True if *text* contains at least one forbidden word."""
    if not text:
        return False
    if not isinstance(text, str):
        return False
    return bool(_get_pattern().search(text))


def get_word_list() -> list[str]:
    """Return the current active word list (from cache or DB)."""
    global _cached_words
    if _cached_words is None:
        _get_pattern()          # populates _cached_words as a side-effect
    return list(_cached_words or _BUILTIN_WORDS)
