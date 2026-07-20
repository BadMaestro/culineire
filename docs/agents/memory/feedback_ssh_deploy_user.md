---
name: feedback-ssh-deploy-user
description: "SSH deploy user is `deploy`, not `culineire`. Key is culineire_linode in WSL ~/.ssh/"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

SSH деплой: пользователь `deploy` (не `culineire`, не `root`).

```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode deploy@80.85.84.156 'cd /srv/culineire/current && set -a && source /srv/culineire/shared/.env && set +a && /srv/culineire/venv/bin/python manage.py migrate --no-input && /srv/culineire/venv/bin/python manage.py collectstatic --no-input && sudo systemctl restart unit'"
```

**Why:** Попытка с `culineire@` давала Permission denied — такого пользователя нет. Реальный deploy user = `deploy` (uid 1000), ключ `culineire_linode` в WSL `~/.ssh/`.

**How to apply:** Всегда использовать `deploy@80.85.84.156`, никогда не `culineire@` или `root@`.
