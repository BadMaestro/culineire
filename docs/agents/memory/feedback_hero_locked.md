---
name: feedback_hero_locked
description: Hero image object-position is PERMANENTLY LOCKED at center 60% — never change without owner approval
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ef9a9e7f-5373-41eb-a548-f17ac0a1525f
---

⛔ NEVER change `object-position` on any hero image across the site without explicit owner approval.

The owner has calibrated all hero positions and is tired of fixing this repeatedly.

**Why:** Hero images were breaking constantly due to agents independently adjusting them. Owner spent significant time fixing. Now locked permanently.

**Golden position:** `center 60%` for all section/listing hero images sitewide.

**How to apply:** If any task touches CSS files that contain hero image rules, check CLAUDE.md first. If `object-position` on a hero differs from the locked value — do NOT fix it silently. Report to owner and wait.

**Locked files:** hero_switcher.css, content_cards.css, pinch.css, newsfeed.css, sponsors.css, monitoring.css, authoring.css, auth.css (hero--legal, hero--inbox), base.css (hero--author-profile).

**Intentional exceptions (also locked):** hero--recipe-detail = `center center`, hero--login = `center 40%`, hero--contact = `center 44%`.

Full reference table in CLAUDE.md under "Hero Image Positioning — LOCKED."

**УТОЧНЕНИЕ владельца 2026-07-05:** Золотое правило hero относится ТОЛЬКО к РАСПОЛОЖЕНИЮ — координатам, где стоят кнопки/хедеры/элементы (pill 49px top, H1 top, padding-block, object-position и т.д.). Другие правки РАЗРЕШЕНЫ без спроса: добавлять новые кнопки, новый функционал, УБИРАТЬ элементы (напр. большую hero-battle-панель), менять содержимое. Нельзя без спроса менять только сами golden-координаты/позиции. То есть «убрать блок из hero и перенести его функции в другой виджет» — можно; «сдвинуть pill с 49px» — нельзя.
