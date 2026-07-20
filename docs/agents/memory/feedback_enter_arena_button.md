---
name: feedback-enter-arena-button
description: Enter Arena button — единственный правильный способ добавить кнопку Arena на любую страницу
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ef9a9e7f-5373-41eb-a548-f17ac0a1525f
---

Всегда используй `{% include '_enter_arena_btn.html' %}` — никогда не хардкодить inline.

**File:** `templates/_enter_arena_btn.html`  
**Content inside:** `<a class="btn-primary" href="{% url 'chef_battle:arena' %}">Enter Arena</a>`  
**Rules:**
- Только `btn-primary` — никогда `btn-secondary`, `text-link`, `battle-back-link` или другой класс
- Только URL `chef_battle:arena` — никакой другой
- 30 instances across 26 templates уже конвертированы через этот include

**Why:** GreenBear зафиксировал это как проектный стандарт в CoWork Shared Memory (July 1, 2026). Единый стиль, единый include, единый URL.

**How to apply:** На любой новой странице где нужна кнопка "Enter Arena" — только `{% include '_enter_arena_btn.html' %}`, ничего больше.
