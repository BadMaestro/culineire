---
name: Verify before confirming
description: Always run git status / check files exist before saying "yes it's ready"
type: feedback
originSessionId: 41497f72-e8fb-41cf-96f0-0946e152a172
---
Never confirm that something is ready to deploy without actually verifying it first — check git status, check the file exists and is tracked.

**Why:** Said "да" (yes, it's all there) when hero-welcome.png was untracked in git. User deploys to prod himself and only adds what's committed. Caused wasted deploy and justified anger.

**How to apply:** Before saying "it's ready" or "yes" to any deploy-readiness question — run `git status` and confirm the relevant files are committed. Don't assume.
