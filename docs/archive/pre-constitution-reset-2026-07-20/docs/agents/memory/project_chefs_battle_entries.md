---
name: project-chefs-battle-entries
description: "Chef's Battle — entries are recipes only, articles not used in battles"
metadata: 
  node_type: memory
  type: project
  originSessionId: 54e34f70-f718-4f1f-a375-9e6d18758d42
---

Записи в Chef's Battle — только рецепты. Статьи не участвуют в боях.

**Why:** Концепт построен вокруг кулинарии — аудитория голосует за лучшее блюдо, поэтому только рецепты имеют смысл как боевые записи.

**How to apply:** Не добавлять поддержку статей в BattleEntry, убрать article-поле если оно мешает логике, в шаблоне показывать только recipe-ветку.
