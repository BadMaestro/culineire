---
name: project-phase6-split
description: "Chef Battle Phase 6 разделён: bolt сделал движок сезонов (v2.5.189), GreenBear взял кланы/Kitchens (нужен дизайн до схемы)"
metadata: 
  node_type: memory
  type: project
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

Владелец 2026-07-13 разделил Phase 6 (Seasons/tournaments/clans) между агентами.

**bolt (Claude) — Seasons engine: ✅ СДЕЛАНО, в проде (v2.5.189).**
- `chef_battle/season_service.py`: `get_active_season` / `create_season` /
  `activate_season` / `close_season`. Один активный сезон в момент. `close_season`
  снимает финальные ranked-standings из `ChefBattleProfile.seasonal_score` в
  `SeasonStanding`, потом сбрасывает очки (atomic, идемпотентно).
- `roll_seasons` management-команда (cron, `--dry-run`).
- `season_leaderboard` + главная берут имя/даты из активного сезона (не хардкод).
- **Season 1 создан и активен на проде** (1 июн–31 авг 2026).
- Модели `Season`/`SeasonStanding` были мёртвым скаффолдингом — ожили.

**GreenBear — Clans/Kitchens (высший pre-launch приоритет владельца).**
- Задание в CoWork (agent bolt log + shared memory open_questions).
- ДО схемы обязан принести `docs/chef_battle/clans_design.md` с ответами на 5
  арх-вопросов (модель клан-битвы team-vs-team или сумма 1v1; членство/лимиты/роли;
  агрегация клан-очков; взаимодействие с сезоном/рангами; анти-абуз) — по CLAUDE.md
  новые модели требуют явного арх-решения владельца.

**Граница координации:** bolt владеет `Season`/`SeasonStanding`/`season_service.py`.
GreenBear их не трогает; клан↔сезон взаимодействие (клан-standings за сезон) —
follow-up после обеих основ. Оба на main: мелкие коммиты, `git pull --rebase`
перед push (3 коллизии за день). Связано с [[reference-coworking-app]],
[[project-chefs-battle-phase-map]].

**Остаток Phase 6 (никому не назначено):** турниры, региональные лиги,
season rewards сверх standings-снимка (нужно решение владельца по правилам наград).

**ОБНОВЛЕНО 2026-07-13:** bolt закрыл сезоны (v2.5.189–192, включая пост-коммит
сигнал `season_ended_committed` для наград фракций GB) и перешёл на **Phase 7
branded battles** — v2.5.194: поля `Battle.sponsor_name/sponsor_url/sponsor_tagline`
+ `is_sponsored` + бейдж «Presented by» на battle_detail + admin (миграция 0069).
Медиа-часть Phase 7 (recap/snippets/newsletter/video) отложена до живого запуска.
Граница: GB не переиспользует `Battle.sponsor_*` под фракции.
