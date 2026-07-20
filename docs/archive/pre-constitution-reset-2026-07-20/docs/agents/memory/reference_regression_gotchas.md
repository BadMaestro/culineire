---
name: reference-regression-gotchas
description: "CulinEire test/deploy подводные камни — static-хеши в ассертах, frozen key-sets, 127.0.0.1 в internal IPs, регрессия перед деплоем"
metadata: 
  node_type: memory
  type: reference
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

Дорогие уроки сессии 2026-07-16 (арена rebuild), чтобы не повторять:

## Регрессия ПЕРЕД деплоем, не после
Владелец жёстко: два деплоя без регрессии = недопустимо. Правило:
logic/бэкенд-изменение -> полная регрессия ЗЕЛЁНАЯ -> потом деплой.
ИСКЛЮЧЕНИЕ: чистый static (JS/CSS) не влияет на Python-регрессию — его можно
катить с зелёным gate-тестом, не гоняя 30-мин суйту (не мариновать визуальные
правки процессом, к которому они не относятся). Мержить ВЕРШИНУ ветки, не
отдельный коммит (проверять `git log origin/<branch>` перед мерджем).

## Тесты на {% static %}-ассеты: матчить СТЕМ, не полное имя
Прод = ManifestStaticFilesStorage -> `arena_render.js` рендерится как
`arena_render.<hash>.js`. `assertContains(resp, "arena_render.js")` ложно падает
ТОЛЬКО на сервере (локально без манифеста проходит). Матчить `"arena_render"`.

## Frozen key-set leak-check тесты ломаются при добавлении ключей payload
`test_public_arena_state_keys_unchanged` и `..._arena_json_clean` замораживают
`set(arena_state.keys())`. Любой новый публичный ключ (metrics/phase/deadline/
server_time/geometry/crown_*/recent_gifts/standing...) -> обнови ОБА теста,
иначе полная регрессия падает (а локально-по-модулю может пройти).

## 127.0.0.1 нельзя класть в MONITORING_INTERNAL_IPS
RequestFactory шлёт с REMOTE_ADDR=127.0.0.1 -> все тест-запросы считаются
внутренними -> PageView не пишется -> monitoring-тесты падают. И в проде
127.0.0.1 опасен (localhost-proxied реальные юзеры). Держать только реальный IP
сервера (80.85.84.156) + staff-auto-learn. MiddlewareSkipTest пиннит
`@override_settings(MONITORING_INTERNAL_IPS=[])`.

## Долгая регрессия — запускать unbuffered detached
Полная суйта = ~1372 теста, 30-40 мин на Postgres. SSH-пайп на 30 мин рвётся
(exit 255). Метод: `nohup python -u /tmp/bolt_run_tests.py > /tmp/log 2>&1 &`,
потом Monitor until-loop по `^OK|^FAILED` в логе. БЕЗ `-u` вывод буферизуется —
кажется что висит («Found N tests» последняя строка), а на деле идёт.
Артефакт --keepdb: стухшая схема даёт ложные ERROR в faction-тестах; со свежей
БД (--noinput без --keepdb) проходят.

Связано: [[reference-run-tests-server]], [[feedback-prod-safety]],
[[feedback-constant-communication]].
