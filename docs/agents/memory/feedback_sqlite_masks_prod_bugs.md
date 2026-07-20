---
name: feedback-sqlite-masks-prod-bugs
description: "Локальные тесты на SQLite маскируют баги, которые падают на Postgres/в проде — проверять отдельно select_for_update+nullable select_related и живые платёжные пути"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

Локальный тест-раннер CulinEire использует in-memory **SQLite**
(`file:memorydb_default?mode=memory`), а прод — **Postgres**. «Все тесты
зелёные» на SQLite ≠ зелёные на проде.

**Why:** За две сессии подряд SQLite скрыл реальные баги:
1. `select_for_update()` + `select_related(<nullable FK>)` → на Postgres
   `FOR UPDATE cannot be applied to the nullable side of an outer join`.
   SQLite команду `select_for_update` вообще игнорирует. Было в
   `operator_end_stream` (battle nullable) — фикс `of=("self",)` в v2.5.186.
2. `handle_token_order_chargeback` имел ДВА латентных бага, не покрытых
   тестами: `wallet__owner` вместо `chef` (FieldError) и
   `TokenTransaction.create(reason=...)` без обязательных
   `tx_type`/`balance_after` (TypeError). Живой путь — Stripe-вебхуки
   `charge.refunded`/`charge.dispute.created`. Полный фикс v2.5.188.

**How to apply:**
- После «все тесты прошли» на SQLite для платёжных/чарджбэк/выплатных путей
  и для любого `select_for_update` — проверять отдельно: либо прогон на
  Postgres, либо ручная компиляция запроса (`str(qs.query)`) + проверка
  имён полей через `Model._meta.get_fields()`.
- Аудитить `select_for_update()` рядом с `select_related` на nullable FK.
- Код без тестов (напр. вебхук-обработчики) читать построчно на соответствие
  реальным именам полей — модель могла разойтись с кодом.
- Проверка nullable FK: `null=True` в модели → LEFT OUTER JOIN → опасно с
  `select_for_update`. Связано с [[feedback-check-before-acting]].
