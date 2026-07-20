---
name: feedback-never-run-as-root-on-server
description: Не гонять manage.py/Django shell на сервере под root — созданные root файлы ломают прод 500-ками; запускать под deploy
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
  modified: 2026-07-19T19:12:42.408Z
---

**Никогда не запускать Django на проде под `root`** — ни `manage.py`, ни shell-проверки,
ни разовые скрипты. Приложение работает под пользователем **`deploy`**.

Правильно:
```
sudo -u deploy /srv/culineire/venv/bin/python ...
```

**Why:** любой файл, созданный root, приложение прочитать не может.
Уже сломало прод дважды:
1. `collectstatic` под root → 662 файла статики root-owned, сайт молча отдавал старый файл.
2. 2026-07-19: мои проверки под root создали 2 файла `/srv/culineire/shared/cache/*.djcache`
   с владельцем root и правами 600 → `PermissionError` в filebased-кеше →
   **500 на логине и других страницах**. Код и деплой были ни при чём.

## ОБЯЗАТЕЛЬНАЯ ПРОВЕРКА — гнать ПОСЛЕ каждого деплоя и после каждого запуска на сервере

```bash
find /srv/culineire/shared/cache /srv/culineire/shared/media \
     /srv/culineire/shared/staticfiles /srv/culineire/shared/logs \
     ! -user deploy 2>/dev/null | head
```
Пусто = чисто. Не пусто = чинить НЕМЕДЛЕННО (`chown deploy:deploy`, кеш можно удалить).

Проверять именно эти 4 каталога, а не весь сервер: в `/srv/culineire/current` сотни
root-owned файлов кода с правами 644 — приложение их читает, это НЕ проблема.
Бэкапы `.env` в `shared/backups/daily/` root-only 600 — так и ДОЛЖНО быть, там секреты,
не «чинить».

**How to apply:** после ЛЮБОГО запуска чего-либо на сервере проверять
`find /srv/culineire/shared -o /srv/culineire/shared/cache ! -user deploy`.
Нашёл — `chown deploy:deploy` (кеш можно просто удалить, он одноразовый).
Симптом «500 там, где ничего не менял» → первым делом искать root-owned файлы,
а не отлаживать код.

Связано: [[reference-deploy-restarted-lies]], [[project-deploy-workflow]],
[[feedback-prod-safety]].
