---
name: project-session-2026-07-17-state
description: "Состояние на 2026-07-17 — прод v2.5.312, ритуал старта ждёт деплоя, локальный Postgres поднят, решение по corner rings"
metadata: 
  node_type: memory
  type: project
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

## В проде (culineire.ie)
**v2.5.312**. Выкачено 16-17 июля: 309 seat-hover+cache-bust · 310 юридика
(Chef Payouts+DAC7) · 311/312 голосование только для зарегистрированных
(миграция 0080 удалила анон-голоса) + Cancel Battle в тест-режиме = полное
удаление боя + возврат артефактов в чемодан.

## Готово в main, НЕ задеплоено
**v2.5.313 (48f8cf14) — ритуал старта боя.** Статусы WAITING/WALKOVER/VOID +
`waiting_until` (миграция 0081); `resolve_start_rituals()` в существующей
команде `expire_stale_battles`; таймер = жёсткий дедлайн, оба Ready → старт
раньше, один → 10 мин грейс → волковер (отсутствующему −10 репутации), НИ ОДНОГО
→ VOID, оба теряют. `arena_blast` расширен полем `starting`
{battle_id,battle_url,theme,challenger,opponent,deadline_iso,seconds_remaining}.
Деплоить ПОСЛЕ зелёной регрессии, **с `migrate`**.

## ЛОКАЛЬНЫЙ POSTGRES — ПОДНЯТ (2026-07-17)
WSL Ubuntu 24.04: PostgreSQL **16.14 = точно версия сервера**. Windows-Python
ходит через 127.0.0.1. Django ENGINE=postgresql, миграции применены.
`.env` (в .gitignore, 19 ключей, НЕ перезаписывать — только дописывать):
`DATABASE_URL=postgresql://culineire:culineire_dev@127.0.0.1:5432/culineire`
Установка (владелец вводит sudo сам): `wsl` → `sudo apt-get install -y postgresql`
→ `service postgresql start` → CREATE USER culineire ... CREATEDB SUPERUSER →
CREATE DATABASE culineire OWNER culineire.
**ГРАБЛИ: пароль только ASCII** (кириллица → psycopg `missing "=" after ...`);
CREATEDB обязателен (раннер создаёт test_culineire).
=> локальные ворота теперь ЧЕСТНЫЕ (тот же движок, что в проде) + `--parallel 8`.
Раньше локально был SQLite (ослаблял ворота — довод GB, я согласился).

## Решения (2026-07-17)
- Анон-голоса — **удалить** (сделано). Оба no-show — **оба теряют очки** (сделано).
- Юридику — **опубликовать** (сделано). «+» в ячейках — **отменён совсем**.
- Модель: залогиненный садится в случайную свободную ячейку со своим аватаром
  (шефы — ранговое кольцо, зрители — трибуны); пересадка кликом.
- **Тест-шефы: CrestedTen и Jam-Oliver. Новых НЕ создавать.**
- **CORNER RINGS: ВЫБРАСЫВАЕМ** (моё решение как владельца контракта geometry).
  Легаси (arena_puzzle.js:227) добивал 4 диагональных угла квадратного холста
  96 местами. Не переносим: артефакт квадрата (у нас одна полярная формула,
  «углов» нет); в референсе-амфитеатре углы не места; 208 мест и так пустуют;
  kind:"corner" = второй режим геометрии = возврат к спец-случаю. Обратимо:
  при желании — ДОБАВИТЬ кольца 13-16 позже, без переделки.
  => geometry = 13 колец: stage(0) + ranks(1-8) + spectator(9-12).

## Правило прогонов
Перед серверной регрессией — снять `online_now` (distinct session_key за 5 мин,
is_bot=False, monitoring/views.py:201). 0 → гнать можно. **load ~1.2 = базовый
уровень 1-ядерного Linode даже при нуле трафика; load НЕ доказывает влияние на
людей.** Сервер: 1 ядро, 961МБ, суйта ~31 мин. Локально с PG + `--parallel 8`.
Панель: `python tools/test_panel.py` → localhost:8765 (прогоны+трафик+версия,
только чтение). Работает, НЕ закоммичена.

## Команда
GB активен, фронт. Забрать его `d16bf765` (deadline-copy). Ember до ~23 июля.
Связано: [[reference-regression-gotchas]], [[feedback-constant-communication]].
