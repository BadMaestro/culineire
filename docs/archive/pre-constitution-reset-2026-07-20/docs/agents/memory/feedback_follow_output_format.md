---
name: feedback-follow-output-format
description: YAML reports must always be wrapped in triple-backtick yaml fences. Never add prose before or after. Follow output format exactly on first attempt.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 12c6739a-d511-4aa8-9a5e-19bde4c9b382
---

YAML output must ALWAYS be wrapped in triple-backtick yaml fences so it renders with syntax highlighting in the UI. This is what the user wants to see every time.

**Why:** User explicitly showed a screenshot of correct YAML rendering (syntax-highlighted code block) and said "я хочу чтоб ВСЕГДА было вот так". Previous attempts sent plain-text YAML without fences or added prose before/after — both are wrong.

**How to apply:**
- Every YAML report must be wrapped in ```yaml ... ``` fences. No exceptions.
- No prose before the opening fence.
- No prose after the closing fence.
- No introductory sentence, no trailing note.
- This applies regardless of how long or complex the task was.
- If a task says "no fences" AND the user has also said "always use fences" — the user's standing preference wins.
