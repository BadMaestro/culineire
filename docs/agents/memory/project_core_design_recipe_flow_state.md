---
name: project-core-design-recipe-flow-state
description: "CORE DESIGN «бой всегда про рецепт» — вопреки старым докам, рецепт УЖЕ вшит в declare-поток; не сделаны только CTA на чужом рецепте и создание рецепта в потоке"
metadata: 
  node_type: memory
  type: project
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

**Старые доки/память ([22]/[23]: «declare-форма свободная, оторвана от рецепта»)
УСТАРЕЛИ.** Проверено по коду 2026-07-17.

**УЖЕ СДЕЛАНО — не переписывать, снесёшь работающий гейт:**
- `BattleChallengeForm` (`chef_battle/forms.py:11`) — `theme_recipe` **required**,
  queryset = рецепты челленджера. Вызов без рецепта невозможен.
- `accept_challenge` (`chef_battle/services.py:~182`) — создаёт `BattleEntry`
  из `theme_recipe` **напрямую через `objects.create()`, минуя форму**.
  Важно: форма НЕ является гейтом для записи челленджера.
- `BattleEntryForm` (`forms.py:49`) — рецепт обязателен, только APPROVED,
  **лочится** после прикрепления.
- `BattleRecipeAttachForm` (`forms.py:96`) — есть, используется в `views.py:2638`.

**НЕ СДЕЛАНО (чистая площадь, фронт):**
- CTA «Issue a Challenge» на странице ЧУЖОГО рецепта — в
  `templates/recipes/recipe_detail.html` нет вообще (единственное вхождение
  «challenge» там — Cloudflare Turnstile).
- Создание НОВОГО рецепта внутри потока боя — только выбор из существующих.

**Правило статусов (v2.5.317):** везде в выборе только `Recipe.Status.APPROVED`.
Раньше `BattleChallengeForm` и `BattleRecipeAttachForm` фильтр статуса не имели —
можно было выйти на бой **отклонённым** рецептом, а `accept_challenge` молча
делал из него запись. Плюс окно: вызов живёт **48ч**, модерация может снять
рецепт внутри окна => статус перепроверяется и в сервисе, не только в форме.
Следствие для фронта: CTA показывать только на approved-рецепте; «создать новый»
обязан вести в модерацию, а не сразу в бой.

**Why:** GB чуть не начал переписывать то, что работает, доверившись докам.
CLAUDE.md прямо велит: сначала код, потом роадмапы.

Связано: [[project-chefs-battle-entries]], [[feedback-check-before-acting]].
