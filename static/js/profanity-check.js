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
        var apiUrl = "/monitoring/profanity/words.json";
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
                        /* Re-sync all already-initialised textareas */
                        document.querySelectorAll("textarea[data-profanity-init]")
                            .forEach(function (ta) {
                                ta.dispatchEvent(new Event("input"));
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
    /*  Init a single textarea                                              */
    /* ------------------------------------------------------------------ */
    function initTextarea(ta) {
        /* Avoid double-init */
        if (ta.dataset.profanityInit) return;
        ta.dataset.profanityInit = "1";

        /* -- wrapper -- */
        var wrapper = document.createElement("div");
        wrapper.className = "profanity-wrapper";

        /* -- backdrop -- */
        var backdrop = document.createElement("div");
        backdrop.className = "profanity-backdrop";
        backdrop.setAttribute("aria-hidden", "true");

        var highlights = document.createElement("div");
        highlights.className = "profanity-highlights";
        backdrop.appendChild(highlights);

        /* Insert wrapper into DOM, move textarea inside it */
        ta.parentNode.insertBefore(wrapper, ta);
        wrapper.appendChild(backdrop);
        wrapper.appendChild(ta);

        /* -- sync function -- */
        function sync() {
            /* Copy layout styles so backdrop overlaps textarea exactly */
            copyStyles(ta, highlights);

            /* Match wrapper and backdrop dimensions to textarea */
            var w = ta.offsetWidth;
            var h = ta.offsetHeight;
            backdrop.style.width  = w + "px";
            backdrop.style.height = h + "px";

            /* Render highlighted text */
            highlights.innerHTML = buildHighlightHtml(ta.value);

            /* Sync scroll position */
            backdrop.scrollTop  = ta.scrollTop;
            backdrop.scrollLeft = ta.scrollLeft;

            /* Block / allow form submission */
            var bad = hasProfanity(ta.value);
            ta.setCustomValidity(bad ? "Text contains forbidden words — please remove them before publishing." : "");

            /* Visual feedback on the textarea border */
            ta.classList.toggle("profanity-active", bad);
        }

        ta.addEventListener("input",  sync);
        ta.addEventListener("scroll", function () {
            backdrop.scrollTop  = ta.scrollTop;
            backdrop.scrollLeft = ta.scrollLeft;
        });

        /* Re-sync when the textarea is resized by the user */
        if (window.ResizeObserver) {
            new ResizeObserver(sync).observe(ta);
        }

        sync();
    }

    /* ------------------------------------------------------------------ */
    /*  Boot                                                                */
    /* ------------------------------------------------------------------ */
    function init() {
        document.querySelectorAll("textarea[data-profanity]").forEach(initTextarea);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
}());
