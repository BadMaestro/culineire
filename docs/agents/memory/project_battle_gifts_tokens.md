---
name: project-battle-gifts-tokens
description: "Система подарков зрителей и токенов в Chef's Battle — цветы/кофе/виски/коктейли/пиво + токен-экономика"
metadata:
  node_type: memory
  type: project
  originSessionId: 54e34f70-f718-4f1f-a375-9e6d18758d42
---

## Токен-экономика

Внутренняя валюта сайта. Пакеты:

| Пакет | Токены | Цена EUR |
|---|---|---|
| Starter | 100T | €10 |
| Popular | 250T | €20 |
| Pro | 600T | €40 |
| Champion | 1400T | €80 |

## Подарки зрителей шефам — два типа

### 1. Боевые артефакты (дарить шефам в бой)
Влияют на бой. Покупаются за токены:

| Редкость | Цена |
|---|---|
| Common | 10T |
| Uncommon | 25T |
| Rare | 60T |
| Epic | 150T |
| Legendary | 400T |

### 2. Артефакты признательности (Appreciation artifacts)
**НЕ влияют на бой.** Остаются на профиле шефа навсегда (permanent showcase).

| Подарок | Цена |
|---|---|
| Flowers (цветы) | 5T |
| Coffee (кофе) | 5T |
| Beer (пиво) | 10T |
| Cocktail (коктейль) | 15T |
| Whiskey (виски) | 20T |

**Why:** Озвучено владельцем 2026-06-11. Зрители могут выражать признательность шефам подарками, которые не дают боевого преимущества.
**How to apply:** Appreciation artifacts = Phase 5+ (после MVP). Токены = Phase 5+. Не реализовывать раньше MVP social loop.
