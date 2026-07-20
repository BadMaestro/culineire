---
name: feedback-ssh-deploy-method
description: Как выполнять деплой и SSH-команды на сервер — правильный метод через Bash tool + WSL с явным ключом
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 54e34f70-f718-4f1f-a375-9e6d18758d42
---

Правильный способ подключиться к серверу и деплоить — НЕ через Ubuntu терминал (computer-use), а через Bash tool напрямую:

```bash
wsl -d Ubuntu -- bash -c "ssh -i /home/golovin/.ssh/culineire_linode -o StrictHostKeyChecking=no deploy@80.85.84.156 'КОМАНДА'" 2>&1
```

Для деплоя:
```bash
wsl -d Ubuntu -- bash -c "ssh -i /home/golovin/.ssh/culineire_linode -o StrictHostKeyChecking=no deploy@80.85.84.156 'cd /srv/culineire/current && bash /srv/culineire/current/deploy/update.sh'" 2>&1
```

**Why:** Ubuntu WSL терминал (computer-use) не принимает clipboard paste корректно — вставляет `^V`, `^M` вместо текста. Bash tool с `wsl -d Ubuntu` работает напрямую и использует SSH-ключ `/home/golovin/.ssh/culineire_linode`.

**How to apply:** При любом запросе "делай деплой" или "запусти на сервере" — сразу использовать Bash tool с командой выше, не открывать Ubuntu через computer-use.
