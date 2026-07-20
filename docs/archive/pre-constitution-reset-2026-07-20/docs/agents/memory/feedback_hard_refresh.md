---
name: Hard refresh after every deploy
description: User always does Ctrl+Shift+R after deploy — never suggest this as a fix
type: feedback
originSessionId: 41497f72-e8fb-41cf-96f0-0946e152a172
---
User always performs Ctrl+Shift+R (hard refresh) after every deploy. This is their standard practice.

**Why:** They know about browser caching and handle it automatically.

**How to apply:** Never suggest Ctrl+Shift+R or browser cache clearing as a troubleshooting step. If CSS/JS changes don't appear after deploy, the root cause is something else (server config, wrong commit, collectstatic failure, etc.) — investigate that instead.
