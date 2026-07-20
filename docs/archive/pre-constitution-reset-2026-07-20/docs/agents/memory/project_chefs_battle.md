---
name: project-chefs-battle
description: "Chef's Battle — текущее состояние реализации (Phase 1+2 завершены, в проде)"
metadata:
  node_type: memory
  type: project
  originSessionId: 54e34f70-f718-4f1f-a375-9e6d18758d42
---

Chef's Battle — PvP кулинарная система. Живёт в `chef_battle/` app. В проде на `main` (не отдельная ветка).
ТЗ документы: `docs/chef_battle/` в репозитории (читать через Read tool).

**Why:** Retention engine — превратить сайт в живую кулинарную PvP-платформу.
**How to apply:** Весь Chef Battle код идёт только в `chef_battle/` app.

## Что реализовано (Phase 1 + 2 — завершено)

**Модели (`chef_battle/models.py`):**
- `ChefBattleProfile` — rank, rating, wins, losses, crown_until, battle_moves, seasonal_score
- `BattleChallenge` — статусы: pending/accepted/refused/expired
- `Battle` — статусы: scheduled/active/menu_locked/cooking/presentation/voting/completed/cancelled + ingredient_penalty
- `BattleEntry`, `BattleVote`, `BattleEvent`
- `TokenWallet`, `TokenTransaction`, `TokenPackage`
- `AppreciationGift`, `BattleArtifact`, `Artifact`, `ChefArtifact`
- `Season`, `SeasonStanding`
- `ChefBattleNotification`, `BattleChat`

**Сервисы:** `chef_battle/services.py`

**Templates (все страницы):**
- `home`, `challenge_form/list`, `battle_detail`, `entry_form`, `biathlon`
- `rankings`, `season_leaderboard`, `appreciation_gallery`, `artifact_gallery`
- `battle_chest`, `changing_room`, `rules`, `token_shop`
- `chef_profile`, `hall_of_fame`, `cooking_submit/moderation`, `notifications_inbox`

**Инфраструктура:**
- Hero battle panel (`_hero_battle_panel.html`) — показывается на всех страницах сайта (кроме legal)
- Context processor `hero_battle_panel` в `config/context_processors.py` (60s cache)
- Cron: `expire_stale_battles` запускается на сервере
- Newsfeed интеграция: события битв → NewsFeedEntry
- Author profile: блок статистики шефа
- Feature flag: `CHEF_BATTLE_ENABLED` в settings

## Текущая фаза

Phase 1 (MVP) + Phase 2 (Social Visibility) — реализованы и в проде.
Phase 3+ (Energy Economy, Combat Engine) — ещё не начаты.
