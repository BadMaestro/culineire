---
name: reference-deploy-restarted-lies
description: "«RESTARTED» не значит «задеплоено» — collectstatic падает тихо, сайт отдаёт старый хешированный файл"
metadata: 
  node_type: memory
  type: reference
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

Деплой печатает `RESTARTED` даже когда `collectstatic` **упал**: команды
соединены через `&&`, но падение post-processing не всегда роняет цепочку, а
вывод про ошибку уходит выше по логу, где его не читают.

Механика тихой поломки: `ManifestStaticFilesStorage` отдаёт сайту **хешированное**
имя (`arena_deck.24e553786a4b.js`). Обычная копия обновляется на первом шаге, а
хешированная — на post-processing. Если post-processing упал, `arena_deck.js`
свежий, а `arena_deck.<hash>.js` и `staticfiles.json` — старые. **Сайт отдаёт
старый код при внешне успешном деплое.**

**Why:** 2026-07-17 (v2.5.314) `collectstatic` упал с `PermissionError` — **662 из
733** файлов статики принадлежали `root`, потому что прошлые деплои гоняли
`collectstatic` под `sudo`, и штатный пользователь `deploy` перестал их
перезаписывать. Поймал только потому, что читал строки выше `RESTARTED`.
Тот же класс, на котором GB погорел с `?v=` (CDN отдавал старый файл).

**How to apply:**
- Владелец статики — `deploy:deploy`. Никогда не запускать `collectstatic` под
  `sudo`. Если права уехали: `sudo chown -R deploy:deploy /srv/culineire/shared/staticfiles`.
- После правки CSS/JS проверять **живой файл**, а не факт рестарта:
  `curl -s https://culineire.ie/static/js/<имя>.<hash>.js | grep -c '<твоя строка>'`
  (хеш брать из `staticfiles.json` на сервере).
- `RESTARTED` — не доказательство. Доказательство — байты с прода.

Связано: [[project-deploy-workflow]], [[reference-regression-gotchas]].
