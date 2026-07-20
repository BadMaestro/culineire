---
name: Button design system — unified structure
description: All new buttons must use the existing site button CSS classes, not custom one-off styles
type: feedback
originSessionId: 41497f72-e8fb-41cf-96f0-0946e152a172
---
All buttons created on the site must use the existing unified button CSS from the start — no custom one-off button styles.

**Why:** Consistency across the UI. Every button should look like it belongs to the same design system. One-off styles (like `.mod-maintenance-btn`) drift from the site's established look and create maintenance debt.

**How to apply:**
- Before styling a new button, find the existing button CSS classes in the project (e.g. `mod-btn`, `mod-btn--approve`, `mod-btn--reject`, etc. in `moderation.css`; or whatever the global button system is)
- Reuse those classes directly — extend only if genuinely needed (e.g. a power-button circle shape)
- Never invent new button class names for something that an existing class already covers
- If the existing system lacks a variant, propose adding it to the shared CSS rather than writing isolated styles
