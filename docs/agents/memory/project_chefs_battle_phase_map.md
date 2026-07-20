---
name: project-chefs-battle-phase-map
description: "Полная фазовая карта Chef's Battle из ARTIFACT 3 — 7 фаз от MVP до Seasons & Clans"
metadata:
  node_type: memory
  type: project
  originSessionId: 54e34f70-f718-4f1f-a375-9e6d18758d42
---

## Фазовая карта Chef's Battle (ARTIFACT 3, Section 14)

| Фаза | Название | Главный результат |
|---:|---|---|
| 0 | Foundation | App, models, services, tests, architecture |
| 1 | MVP Battle Core | Challenge, battle room, submission, voting, result, rating, crown |
| 2 | Social Visibility | Homepage feed, profile activity, notifications, battle history |
| 3 | Energy Economy | Earned battle moves from recipes/articles/likes/wins |
| 4 | Combat Engine | Attack/block/missed hit/partial defence mechanics |
| 5 | Artifacts & Cosmetics | Earned artifacts, premium cosmetics, profile prestige |
| 6 | Seasons & Clans | Seasonal rankings, tournaments, kitchens/clans, regional leagues |
| 7 | Sponsorship & Media | Sponsored battles, recaps, social content, commercial events |

## Ключевые принципы (из ARTIFACT 1)

- Артефакты зарабатываются через геймплей, не покупаются напрямую
- Battle points / energy зарабатываются через одобренную активность на платформе
- "Avoid obvious pay-to-win mechanics"
- Победитель битвы = только аудитория (public vote)

## Ранговая лестница

Kitchen Porter → Prep Cook → Commis Chef → Chef de Partie → Sous Chef → Head Chef → Executive Chef → Culinary Master

## Модели по фазам

- Фазы 1-2: ChefBattleProfile, BattleChallenge, Battle, BattleEntry, BattleVote, BattleEvent
- Фаза 3: BattleMoveTransaction (energy/moves ledger)
- Фаза 5: Artifact, ChefArtifact, CosmeticItem, ChefCosmetic
- Фаза 6: Season, SeasonStanding, KitchenClan, KitchenMembership

**Why:** Официальные ТЗ документы из ARTIFACT 1/2/3 в E:\CulinEire Project\Legal and Manuals\PROMPTS\
**How to apply:** Перед реализацией новых фич проверять что фаза правильная; не начинать Phase 4+ без стабильной Phase 1-2.
