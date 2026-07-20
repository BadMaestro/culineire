---
name: Blue annotations in screenshots are hints
description: When user draws in blue on a screenshot, it's a hint for alignment/measurement/removal — not a bug report
type: feedback
originSessionId: 41497f72-e8fb-41cf-96f0-0946e152a172
---
When the user draws in blue on a screenshot, it is always a HINT or GUIDE, not a report of a bug or artifact.

Blue marks typically mean:
- **Lines / equals signs** → "these two things should be equal / aligned"
- **Arrows** → "this element should move in this direction"
- **X marks** → "remove this" or "this gap/element is wrong"
- **Question marks / brackets** → "what is happening here? explain or fix this"
- **Circles / highlights** → "focus on this element"

**Why:** User communicates visually and expects the assistant to interpret the annotation correctly rather than treating the drawn marks themselves as bugs or artifacts.

**How to apply:** Before responding to a screenshot, identify all blue annotations and correctly interpret their meaning in context. Never mistake the drawn annotations for on-screen UI elements.
