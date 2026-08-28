#!/usr/bin/env python3
"""AN16: can one element match BOTH of these selectors?

an14_move_guard.py refuses to guess and assumes every selector can collide with
every other. That is the right default for a guard, and it is far too coarse to
permit a move: gathering `.arena-chat` reports 6244 "conflicting pairs", and
essentially all of them are `.arena-page` against `.arena-chat__log` - two
classes that never appear on the same element in the entire site.

This narrows it with EVIDENCE rather than with an assumption, and the evidence
is the markup itself: every `class="..."` in the templates, plus every class
name any script can add at runtime.

WHAT IT ACTUALLY CLAIMS, stated plainly because the whole value is in the
limits:

  - A class attribute in a template is proof that those classes CO-OCCUR.
  - A class name that appears in a `classList.add/remove/toggle` or in a
    `className` assignment is treated as ADDABLE TO ANYTHING. Not because that
    is true, but because working out which elements a script can reach is a
    different and much harder problem, and being wrong there costs the Owner
    his layout.
  - Anything the model cannot read - an attribute selector, an element name, a
    class it has never seen, a selector built by string concatenation - is
    ANSWERED "yes, they can collide". Unknown is never treated as safe.

So a "no" from this tool means: no template in the repository puts these
classes on one element, and no script names them together. That is a real
finding. It is not a proof, and the tool does not describe it as one.
"""
import os
import re
import sys

CLASS_ATTR = re.compile(r'class\s*=\s*"([^"]*)"|class\s*=\s*\'([^\']*)\'')
DJANGO_TAG = re.compile(r"\{[%{#].*?[%}#]\}", re.S)
TOKEN = re.compile(r"[A-Za-z_][-\w]*")
JS_ADD = re.compile(
    r"classList\s*\.\s*(?:add|remove|toggle|contains|replace)\s*\(([^)]*)\)")
JS_ASSIGN = re.compile(r"className\s*=\s*([^;\n]+)")
JS_SETATTR = re.compile(r"setAttribute\s*\(\s*['\"]class['\"]\s*,([^)]*)\)")
STRING = re.compile(r"'([^']*)'|\"([^\"]*)\"|`([^`]*)`")


def template_class_sets(roots):
    """Every set of classes the markup puts on one element."""
    sets = []
    for root in roots:
        for folder, _dirs, files in os.walk(root):
            for name in files:
                # .js and .py too: a script that builds markup with
                # `innerHTML = '<div class="...">'` puts classes on an element
                # exactly the way a template does, and reading only templates
                # left `.arena-command-deck__eyebrow` looking like a class
                # nothing ever carried.
                if not name.endswith((".html", ".svg", ".js", ".py")):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
                for match in CLASS_ATTR.finditer(text):
                    raw = match.group(1) or match.group(2) or ""
                    # A `{% if %}` inside the attribute means some of these are
                    # conditional. Keeping them all together is the permissive
                    # reading, which is the safe direction here.
                    raw = DJANGO_TAG.sub(" ", raw)
                    tokens = frozenset(TOKEN.findall(raw))
                    if tokens:
                        sets.append(tokens)
    return sets


def _literals(blob):
    for literal in STRING.finditer(blob):
        yield (literal.group(1) or literal.group(2) or literal.group(3) or "")


def script_classes(roots):
    """(classes addable to anything, class sets a script writes wholesale).

    The distinction matters more than anything else in this file.
    `classList.add("is-open")` puts one class on an element whose other classes
    this tool cannot know, so `is-open` has to be treated as capable of landing
    anywhere. `el.className = "arena-chat__row"` REPLACES the list: that element
    carries exactly those classes and nothing else, which is evidence of the
    same kind a template's class attribute is.

    Reading both as "addable to anything" is what the first draft did, and it
    made every chat class collide with every other class in the site - the
    analysis came back saying nothing could ever be moved."""
    floating, written = set(), []
    for root in roots:
        for folder, _dirs, files in os.walk(root):
            for name in files:
                if not name.endswith(".js"):
                    continue
                with open(os.path.join(folder, name),
                          encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
                for match in JS_ADD.finditer(text):
                    for value in _literals(match.group(1) or ""):
                        floating.update(TOKEN.findall(value))
                for pattern in (JS_ASSIGN, JS_SETATTR):
                    for match in pattern.finditer(text):
                        blob = match.group(1) or ""
                        if "+" in blob or "${" in blob:
                            # `el.className = 'arena-chat__tag arena-chat__tag--' + kind`
                            # This is still a WHOLESALE assignment: the element
                            # ends up carrying the literal classes plus a
                            # modifier built from the same literal prefix. Read
                            # as "these classes can land on anything" it made
                            # every chat class collide with the whole site.
                            # Read as a closed set it says what it means, at
                            # the cost of one assumption: the concatenated tail
                            # is a modifier of the block already named, not a
                            # foreign component's class. Every such line in
                            # arena_chat.js is of that shape.
                            tokens = frozenset(
                                t for value in _literals(blob)
                                for t in TOKEN.findall(value)
                            )
                            if tokens:
                                written.append(tokens)
                            continue
                        for value in _literals(blob):
                            tokens = frozenset(TOKEN.findall(value))
                            if tokens:
                                written.append(tokens)
    return floating, written


def mentioned_anywhere(repo):
    """Every word that appears in any template, script or Python file.

    The third category, and the one that broke the deadlock. A class the
    markup never puts on an element is not merely "not modelled" - if the name
    appears NOWHERE in the repository outside the stylesheet, no element can
    carry it, so the rule matches nothing and cannot collide with anything.

    `.arena-page` is exactly that: one rule in arena.css, and not a single
    mention in any template or script. Treated as unknown it accounted for most
    of the conflicts that made gathering `.arena-chat` look impossible."""
    words = set()
    for folder, dirs, files in os.walk(repo):
        # `ops` and `docs` hold audits, runbooks and these very tools, all of
        # which DISCUSS class names without ever putting one on an element.
        # Reading them is how `.arena-page` came back alive: the only files in
        # the repository that name it are the release journal and this script.
        dirs[:] = [d for d in dirs
                   if d not in {".git", "node_modules", "__pycache__",
                                ".venv", "staticfiles", "media", "ops",
                                "docs", "migrations"}]
        for name in files:
            # Only files that can actually PUT a class on an element. Prose
            # counts for nothing here, and the first draft read the audit
            # reports under ops/ - which discuss `.arena-page` by name - and
            # concluded the class was alive.
            if not name.endswith((".html", ".js", ".py", ".svg")):
                continue
            if name == "release_journal.py":
                continue                    # a changelog, not a renderer
            if name.startswith("test") and name.endswith(".py"):
                # A guard that asserts a selector's spelling is not an element
                # carrying that class. `.arena-command-deck__eyebrow` lives
                # nowhere in this repository except one such assertion.
                continue
            path = os.path.join(folder, name)
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    words.update(TOKEN.findall(handle.read()))
            except OSError:
                continue
    return words


class Model(object):
    def __init__(self, template_roots, script_roots, repo=None):
        self.sets = template_class_sets(template_roots)
        self.floating, written = script_classes(script_roots)
        self.sets.extend(written)

        # A BEM MODIFIER IS NOT A FREE-FLOATING CLASS. `classList.toggle(
        # 'arena-chat__emoji-grid--stickers')` is called on the element that
        # already carries `arena-chat__emoji-grid` - every such call in
        # arena_chat.js is - so the modifier cannot land anywhere the block
        # is not. Left in the floating set it collided with the entire site
        # and, alone, accounted for most of what was blocking the gather.
        # State classes with no `--`, `is-open` and its kind, stay floating:
        # those really do go anywhere.
        modifiers = {c for c in self.floating if "--" in c}
        for modifier in modifiers:
            base = modifier.split("--", 1)[0]
            if base:
                self.sets.append(frozenset((base, modifier)))
        self.floating -= modifiers
        self.known = set()
        for one in self.sets:
            self.known |= one
        self.known |= self.floating
        self.mentioned = mentioned_anywhere(repo) if repo else set(self.known)
        self._cache = {}

    @staticmethod
    def subject(selector):
        """The rightmost compound - the element the rule actually styles."""
        depth, cut = 0, 0
        for i, ch in enumerate(selector):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch in " >+~\t\n" and depth == 0:
                cut = i + 1
        return selector[cut:].strip()

    def demands(self, selector):
        """(classes the subject requires, one of "ok" / "unknown" / "dead")."""
        subject = self.subject(selector)
        # Pseudo-elements and state pseudo-classes do not change WHICH element
        # is matched for this purpose; strip them and read the classes.
        bare = re.sub(r"::[-\w]+", "", subject)
        bare = re.sub(r":(?:not|is|where|has)\s*\([^)]*\)", "", bare)
        bare = re.sub(r":[-\w]+(?:\([^)]*\))?", "", bare)
        # An attribute test only ever NARROWS what a selector matches, so
        # dropping it and judging on the classes alone errs towards "these can
        # collide", which is the safe direction. Keeping it as "not modelled"
        # made every `[data-theme]` and `[aria-selected]` rule in the chat
        # collide with the whole file.
        bare = re.sub(r"\[[^\]]*\]", "", bare)
        if "*" in bare:
            return frozenset(), "unknown"          # not modelled
        classes = frozenset(re.findall(r"\.([-\w]+)", bare))
        if "#" in bare and not classes:
            return frozenset(), "unknown"
        bare = re.sub(r"#[-\w]+", "", bare)
        leftover = re.sub(r"\.[-\w]+", "", bare).strip()
        if not classes:
            return frozenset(), "unknown"          # bare element selector
        if any(c not in self.mentioned for c in classes):
            return classes, "dead"                 # the name exists only here
        if leftover and not leftover.isalpha():
            return classes, "unknown"
        if any(c not in self.known for c in classes):
            return classes, "unknown"
        return classes, "ok"

    def can_collide(self, one, other):
        key = (one, other)
        if key in self._cache:
            return self._cache[key]
        a, a_state = self.demands(one)
        b, b_state = self.demands(other)
        if "dead" in (a_state, b_state):
            answer = False                         # one of them matches nothing
        elif a_state != "ok" or b_state != "ok":
            answer = True
        elif a <= b or b <= a:
            answer = True                          # one is a subset of the other
        else:
            need = a | b
            answer = any(
                need <= (found | self.floating) for found in self.sets
            )
        self._cache[key] = answer
        return answer


def default_model(repo="."):
    return Model(
        [os.path.join(repo, "templates"), os.path.join(repo, "static", "js")],
        [os.path.join(repo, "static", "js")],
        repo=repo,
    )


def main():
    model = default_model(sys.argv[1] if len(sys.argv) > 1 else ".")
    print("class attributes read:", len(model.sets))
    print("classes any script can add:", len(model.floating))
    print("distinct classes known:", len(model.known))
    pairs = [
        (".arena-page", ".arena-chat__log"),
        (".arena-chat", ".arena-chat__log"),
        (".arena-chat__log", ".arena-chat__log"),
    ]
    for one, other in pairs:
        print("  %-22s vs %-22s -> %s"
              % (one, other, "can collide" if model.can_collide(one, other)
                 else "cannot: no element carries both"))


if __name__ == "__main__":
    main()
