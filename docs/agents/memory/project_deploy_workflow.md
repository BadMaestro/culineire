---
name: project_deploy_workflow
description: "Полный процесс деплоя на прод — команда, SSH-ключ, структура сервера"
metadata: 
  node_type: memory
  type: project
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

## Команда деплоя (единственный правильный способ)

```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'bash /srv/culineire/scripts/deploy.sh 2>&1'"
```

- SSH ключ: `~/.ssh/culineire_linode` (внутри WSL, user golovin)
- Пользователь: **root** (ключ прописан в /root/.ssh/authorized_keys)
- `deploy.sh` делает всё сам: git pull → check → migrate → collectstatic → systemctl restart unit → health check

**Why:** На сервере есть `/srv/culineire/scripts/deploy.sh` — он делает полный цикл включая health check на https://www.culineire.ie/. Не нужно ничего делать вручную.

**How to apply:** Перед деплоем — bump версии в `templates/base.html` (патч v2.5.X → v2.5.X+1), коммит, push. Потом одна команда выше.

## Частая проблема: untracked файлы блокируют deploy.sh

`deploy.sh` проверяет `git status --porcelain` и падает если рабочее дерево не чистое. Если на сервере есть untracked файлы — нужно либо добавить их в git (если должны быть в репо) либо удалить.

## Структура сервера

- `/srv/culineire/current` — git checkout
- `/srv/culineire/venv` — Python virtualenv  
- `/srv/culineire/shared/.env` — production secrets
- `/srv/culineire/shared/staticfiles/` — collected static files
- `/srv/culineire/scripts/deploy.sh` — скрипт деплоя
- IP: **80.85.84.156**, домен: culineire.ie

## Прочее

- `wsl -e bash -c` работает (проверено 2026-07-03)
- Если git push отклонён (rejected) — сделать `git pull --rebase origin main` потом push снова
- Несколько агентов могут пушить параллельно — всегда `git pull --rebase` перед push
