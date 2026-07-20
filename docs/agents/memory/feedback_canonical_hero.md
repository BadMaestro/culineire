---
name: feedback-canonical-hero
description: "Канонический hero сайта — hero hero--home hero--{variant}, НЕ battle-room-hero; эталон company-information и авторский профиль"
metadata:
  node_type: memory
  type: feedback
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

Корпоративный шаблонный hero сайта — это `hero hero--home hero--{variant}` (LOCKED-структура из CLAUDE.md), НЕ `battle-room-hero`. Эталонные страницы: `/legal/company-information/` (templates/legal/company_information.html) и авторский профиль (templates/recipes/author_detail.html).

**Структура:**
```
<section class="hero hero--home hero--{variant}{% if chef_battle_enabled %} hero--has-battle{% endif %}">
  <div class="hero__background"><picture>…<img></picture></div>
  <div class="hero__overlay"></div>
  <div class="container hero__inner">
    <div class="hero-copy">
      <span class="pill">кикер</span>
      {# для профилей: <div class="hero-author-avatar-wrap"><img class="hero-author-avatar">…</div> #}
      <h1 class="hero-title">…</h1>
      <p class="hero-subtitle">…</p>
      <div class="hero__actions"><a class="btn-primary">…</a><a class="btn-secondary">…</a></div>
    </div>
    {% include '_hero_battle_panel.html' %}
  </div>
</section>
```

**ГЛАВНОЕ ПРАВИЛО (владелец, 2026-07-07):** все страницы сайта КРОМЕ баттл-страниц
используют ВСЕ классы главной страницы (home.html, hero--index). Эталон = hero
главной, не company-information. В частности ряд кнопок = `hero__actions >
hero__burger + hero__actions-list` со стандартной навигацией (Pinch / Explore
Recipes / Read Articles / Sponsors). НЕ голый `hero__actions` с произвольными
кнопками, НЕ одиночная контекстная кнопка. Канонический блок вынесен в
`templates/includes/hero_actions.html` — подключать `{% include %}`, не форкать.

**Кнопки:** только `btn-primary` (главное) / `btn-secondary` (второстепенное) / `text-link` (subtle) / `.btn`. НИКАКИХ one-off классов — `btn-ghost` был one-off (2 использования), заменён на `text-link`. Enter Arena — только `{% include '_enter_arena_btn.html' %}`.

**Тело:** семантические секции с существующими классами, `page-section` + `container battle-page` для Chef Battles, НОЛЬ inline-стилей.

**Дизайн-токены (base.css :root):** тёплые кремовые тона — `--bg:#faf6f0`, `--surface:#fffdf9`, `--ink:#1f2c25`, `--muted:#66746d`, `--brand:#8b7355` (коричневый, НЕ зелёный), `--radius-pill:999px`, `--font-serif: Playfair Display`.

**Why:** Владелец указал на company-information как эталон «по нашим правилам». Профиль шефа был на устаревшем `battle-room-hero` — переделан на канонический hero (v2.5.120). См. [[feedback-button-design-system]] и [[feedback-style-sync]].

**How to apply:** Любая новая/правимая страница — начинать с `hero hero--home hero--{variant}` по образцу company_information.html; `content_cards.css` (где `hero-author-avatar-wrap`) грузится глобально через @import в base.css, так что классы доступны везде. Golden-значения hero НЕ трогать (49px pill top и т.д. — LOCKED), только переиспользовать структуру.
