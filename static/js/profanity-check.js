/**
 * profanity-check.js
 *
 * For every <textarea data-profanity> on the page:
 *   - wraps it in a positioned container
 *   - inserts a backdrop <div> behind it that mirrors the text
 *   - forbidden words are rendered with a red wavy underline in the backdrop
 *   - the textarea itself stays fully transparent (background only) so the
 *     underline shows through while the author can still read and edit normally
 *   - sets setCustomValidity() so form-validator.js blocks the submit button
 *
 * Word list is fetched from /monitoring/profanity/words.json on page load
 * so admin-added custom words are picked up immediately without a deploy.
 * Falls back to a hardcoded list if the fetch fails.
 */
(function () {
    "use strict";

    /* ------------------------------------------------------------------ */
    /*  Fallback word list (used if API fetch fails)                       */
    /*  Keep in sync with config/profanity.py _BUILTIN_WORDS              */
    /* ------------------------------------------------------------------ */
    var FALLBACK_WORDS = [
        "fuck","fucked","fucker","fucking","fucks","fuckin",
        "motherfucker","motherfucking",
        "cunt","cunts",
        "shit","shits","shitty","shitting","bullshit","shite",
        "bitch","bitches",
        "bastard","bastards",
        "asshole","assholes","arsehole","arseholes",
        "dickhead","dickheads",
        "prick","pricks",
        "wanker","wankers","wank","wanking",
        "twat","twats",
        "bollocks",
        "whore","whores",
        "slut","sluts",
        "nigger","niggers","nigga","niggas",
        "kike","kikes",
        "chink","chinks",
        "spic","spics",
        "gook","gooks",
        "wetback","wetbacks",
        "raghead","ragheads",
        "towelhead",
        "zipperhead",
        "faggot","faggots",
        "tranny","trannies",
        "retard","retarded","retards",
        "spastic"
    ];

    /* Active regex — starts with fallback, replaced when API responds */
    var _regex = buildRegex(FALLBACK_WORDS);

    function buildRegex(words) {
        if (!words || !words.length) return null;
        return new RegExp(
            "\\b(" +
            words.map(function (w) {
                return w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
            }).join("|") +
            ")\\b",
            "gi"
        );
    }

    /* Fetch the live word list from the API and replace the regex */
    (function fetchWordList() {
        var apiUrl = window.PROFANITY_WORDS_URL || "/monitoring/profanity/words.json";
        if (!window.fetch) return;  // IE11 fallback: just use FALLBACK_WORDS
        fetch(apiUrl, { credentials: "same-origin" })
            .then(function (res) {
                if (!res.ok) throw new Error("words.json " + res.status);
                return res.json();
            })
            .then(function (data) {
                if (data && Array.isArray(data.words) && data.words.length) {
                    var newRegex = buildRegex(data.words);
                    if (newRegex) {
                        _regex = newRegex;
                        /* Re-sync all already-initialised fields */
                        document.querySelectorAll("[data-profanity-init]")
                            .forEach(function (el) {
                                el.dispatchEvent(new Event("input"));
                            });
                    }
                }
            })
            .catch(function () {
                /* Silently keep FALLBACK_WORDS regex */
            });
    }());

    /* ------------------------------------------------------------------ */
    /*  Helpers                                                             */
    /* ------------------------------------------------------------------ */
    function escapeHtml(str) {
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function buildHighlightHtml(text) {
        /* Reset lastIndex because the regex is global */
        _regex.lastIndex = 0;
        var escaped = escapeHtml(text);
        /* Reset again after escapeHtml (no regex used there, but be safe) */
        _regex.lastIndex = 0;
        var html = escaped.replace(_regex, function (match) {
            return '<mark class="profanity-mark">' + escapeHtml(match) + "</mark>";
        });
        /* Trailing space prevents the last line from collapsing */
        return html + " ";
    }

    function hasProfanity(text) {
        _regex.lastIndex = 0;
        return _regex.test(text);
    }

    /* ------------------------------------------------------------------ */
    /*  Copy the typographic styles that affect text layout from textarea  */
    /*  to the backdrop so they overlap pixel-perfectly.                   */
    /* ------------------------------------------------------------------ */
    var STYLE_PROPS = [
        "fontFamily", "fontSize", "fontWeight", "fontStyle",
        "lineHeight", "letterSpacing", "wordSpacing",
        "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
        "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth",
        "borderTopStyle", "borderRightStyle", "borderBottomStyle", "borderLeftStyle",
        "boxSizing", "tabSize"
    ];

    function copyStyles(from, to) {
        var cs = window.getComputedStyle(from);
        STYLE_PROPS.forEach(function (prop) {
            to.style[prop] = cs[prop];
        });
    }

    /* ------------------------------------------------------------------ */
    /*  Init a single field (textarea or input)                            */
    /* ------------------------------------------------------------------ */
    function initField(el) {
        /* Avoid double-init */
        if (el.dataset.profanityInit) return;
        el.dataset.profanityInit = "1";

        var isTextarea = el.tagName.toLowerCase() === "textarea";

        /* -- wrapper -- */
        var wrapper = document.createElement("div");
        wrapper.className = "profanity-wrapper";
        if (!isTextarea) wrapper.classList.add("profanity-wrapper--input");

        /* -- backdrop -- */
        var backdrop = document.createElement("div");
        backdrop.className = "profanity-backdrop";
        backdrop.setAttribute("aria-hidden", "true");

        var highlights = document.createElement("div");
        highlights.className = "profanity-highlights";
        if (!isTextarea) highlights.classList.add("profanity-highlights--input");
        backdrop.appendChild(highlights);

        /* Insert wrapper into DOM, move element inside it */
        el.parentNode.insertBefore(wrapper, el);
        wrapper.appendChild(backdrop);
        wrapper.appendChild(el);

        /* -- sync function -- */
        function sync() {
            /* Copy layout styles so backdrop overlaps element exactly */
            copyStyles(el, highlights);

            /* For single-line inputs: override wrapping */
            if (!isTextarea) {
                highlights.style.whiteSpace = "nowrap";
                highlights.style.overflow   = "hidden";
            }

            /* Match backdrop dimensions to element */
            var w = el.offsetWidth;
            var h = el.offsetHeight;
            backdrop.style.width  = w + "px";
            backdrop.style.height = h + "px";

            /* Render highlighted text */
            var text = isTextarea ? el.value : el.value;
            highlights.innerHTML = buildHighlightHtml(text);

            /* Sync scroll position */
            if (isTextarea) {
                backdrop.scrollTop  = el.scrollTop;
                backdrop.scrollLeft = el.scrollLeft;
            } else {
                backdrop.scrollLeft = el.scrollLeft;
            }

            /* Block / allow form submission */
            var bad = hasProfanity(el.value);
            el.setCustomValidity(bad ? "Text contains forbidden words — please remove them before publishing." : "");

            /* Visual feedback */
            el.classList.toggle("profanity-active", bad);
        }

        el.addEventListener("input",  sync);
        el.addEventListener("scroll", function () {
            if (isTextarea) {
                backdrop.scrollTop  = el.scrollTop;
            }
            backdrop.scrollLeft = el.scrollLeft;
        });

        /* Re-sync when element is resized (textarea only) */
        if (isTextarea && window.ResizeObserver) {
            new ResizeObserver(sync).observe(el);
        }

        sync();
    }

    /* ------------------------------------------------------------------ */
    /*  Boot                                                                */
    /* ------------------------------------------------------------------ */
    function init() {
        document.querySelectorAll("[data-profanity]").forEach(initField);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
}());
