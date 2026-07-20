---
name: reference-arena-build-board
description: "Arena Build board — доска строительства арены с колонками backend/frontend и кнопкой START, шлющей сигнал обоим агентам"
metadata: 
  node_type: memory
  type: reference
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
  modified: 2026-07-19T17:39:38.531Z
---

**URL:** `https://culineire.ie/recipes/moderation/arena-build-plan/` (owner-gated,
`can_grant_bearseeker_privileges` → аноним получает 404, это норма). Построена в v2.5.332
по заказу владельца, по образцу Arena Master Console Plan.

**Что показывает:** все стадии строительства арены, **старые сверху, пронумерованы**, в двух
колонках — **BACKEND (Bolt) слева / FRONTEND (GB) справа**, у каждой стадии прописана
**зависимость** (какой фронт от какого бэка зависит). Зелёный бейдж «готово 100%» — только для
того, что **сдано и задеплоено в прод**. У неготовых — **большая красная кнопка START**.

**START:** POST на `recipes:arena_build_start` → создаёт живое `CoworkingMessage` от `owner`
**обоим** агентам (bolt + greenbear) с текстом стадии, backend/frontend задачами и зависимостью.
Кнопка перекликабельна — владелец жмёт повторно, сигнал уходит снова.

**Где данные:** `ARENA_BUILD_STAGES` в `recipes/views.py` — список dict со стадиями; у каждой
`backend`/`frontend` с полем `done`. Зелёным стадия становится, когда **оба** `done=True`.
Обновлять done-флаги руками по мере деплоев. Шаблон: `templates/moderation/arena_build_plan.html`
(стили и JS встроены). Тесты: `recipes.tests.ArenaBuildPlanTests` (4).

**Важно:** доска — снимок, она не детектит деплой автоматически. После каждого арена-релиза
синхронизировать `done`-флаги, иначе владелец видит красным то, что уже сдано.

Связано: [[project-session-2026-07-19-state]], [[reference-journal-locations]].
