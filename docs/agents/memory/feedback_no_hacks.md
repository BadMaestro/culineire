---
name: No hacks — only proper fixes
description: Never implement workarounds or hacks. Always find the real root cause, research if needed.
type: feedback
originSessionId: 41497f72-e8fb-41cf-96f0-0946e152a172
---
No hacks or workarounds allowed — ever. Only proper fixes.

**Why:** Hacks accumulate technical debt. The user will later have to hunt them down and fix them properly, wasting time.

**How to apply:**
- Before writing a fix, identify the REAL root cause, not a symptom
- If the root cause is unclear, research it (web search, docs) before touching code
- If unsure whether a solution is a hack or a fix — stop and think. A fix addresses the cause; a hack works around the symptom
- It does not matter how long finding the real fix takes — do not cut corners
- Examples of hacks to never do:
  - Disabling CSS transitions before measuring to "stabilize" a reading
  - Double requestAnimationFrame to "wait a bit longer"
  - Adding magic pixel offsets or thresholds without understanding why they are needed
  - Using setTimeout to defer work that should be triggered by a proper event
