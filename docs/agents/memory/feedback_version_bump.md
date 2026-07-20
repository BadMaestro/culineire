---
name: Bump release version before every deploy
description: Before each deploy, increment the patch version in base.html footer (e.g. 1.4.1 -> 1.4.2)
type: feedback
originSessionId: 41497f72-e8fb-41cf-96f0-0946e152a172
---
Before every deploy, increment the patch version number in `templates/base.html` footer.

Current format: `CulinEire Release X.Y.Z`
Pattern: increment Z by 1 with each deploy (1.4.1, 1.4.2, 1.4.3, etc.)

**Why:** User wants the footer to reflect the current release so it's always up to date after each deploy.

**How to apply:** When committing and pushing changes that will be deployed, find the version string in `templates/base.html` and bump the patch number before the final commit.

**CRITICAL: The version bump MUST be included in the same commit as the feature/fix changes.** Do not forget it and add it as a separate commit afterwards. The correct workflow is:
1. Make the feature/fix changes
2. Bump the patch version in `templates/base.html`
3. `git add` both the feature files AND `templates/base.html` together
4. Commit everything in one go

Never bump the version in a follow-up commit after the main feature commit — it must always be part of the same atomic commit.

**ЗОЛОТОЕ ПРАВИЛО (после каждого сжатия диалога перечитывать):** Версию бампает ТОЛЬКО ИИ-ассистент, автоматически, без напоминания пользователя. Это не задача пользователя. Если забыл — это ошибка ассистента.
