---
name: incident_cache_ownership_500
description: Прод упал в 500 из-за владельца файлов в filebased cache; воркер под deploy
metadata: 
  node_type: memory
  type: project
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

2026-07-14: весь сайт упал в 500. Причина — файлы в `/srv/culineire/shared/cache/`
(Django filebased cache) имели владельца, которого веб-воркер не мог прочитать →
`PermissionError` в `config/context_processors.py` (`hero_battle_panel` строка ~93 и
`hero_chef_promotions` строка ~9 вызывают `cache.get()` на КАЖДОЙ странице) → 500 везде.

**Ключевой факт:** приложение `culineire` в NGINX Unit работает под юзером
**`deploy:deploy`** (конфиг: `user=deploy group=deploy`). Значит кэш-файлы ДОЛЖНЫ быть
`deploy:deploy`. Проверить app-юзера: `ps -eo user,pid,args | grep "unit:"` (строки
`"culineire" application`) или control-сокет `/var/run/control.unit.sock /config/applications`.

**Фикс при таком 500:**
```
sudo chown deploy:deploy /srv/culineire/shared/cache
sudo chmod 2775 /srv/culineire/shared/cache      # setgid, новые файлы не уплывают
sudo rm -f /srv/culineire/shared/cache/*.djcache # воркер перегенерит под deploy
```

**Что это спровоцировало (мой факап):** я запускал рендер страниц через `manage.py shell`
по SSH под `deploy`, чтобы «показать» визуал фичи — это писало кэш-файлы и создало
смешанную принадлежность владельцев в папке.

**ПРАВИЛО:** НЕ рендерить страницы через Django `shell`/test-Client на проде. Визуал живой
фичи проверять ТОЛЬКО реальным HTTP (curl / браузер), не через shell. Чистый ORM-query/delete
в shell безопасен (кэш не трогает), рендер — нет. См. [[feedback_no_local_testing]].
