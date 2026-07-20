---
name: Maintenance mode — как включить и выключить
description: Пошаговая процедура включения и выключения maintenance mode на сервере через .env + systemctl restart unit
type: reference
originSessionId: 41497f72-e8fb-41cf-96f0-0946e152a172
---
## Как устроено

Maintenance mode управляется тремя переменными в `.env` на сервере:
- `DJANGO_MAINTENANCE_MODE=True/False` — включить/выключить
- `DJANGO_MAINTENANCE_UNTIL=<ISO 8601 UTC>` — время окончания для таймера на странице (формат: `2026-05-21T15:30:00Z`)
- `DJANGO_MAINTENANCE_RETRY_AFTER_SECONDS=10800` — секунд до повтора (по умолчанию 3 часа = 10800)

Файл `.env` на сервере: `/srv/culineire/shared/.env`

Middleware: `config/maintenance.py` — `MaintenanceModeMiddleware` — читает `settings.MAINTENANCE_MODE` на каждый запрос. Нужен рестарт Unit чтобы новые env-значения подхватились.

Страница maintenance: `templates/maintenance.html` — показывает таймер обратного отсчёта, форму "записки на двери" и ответы.

---

## ВКЛЮЧИТЬ maintenance (N часов)

```bash
# 1. Посчитать время окончания (заменить 3 на нужное количество часов)
UNTIL=$(date -u --date='+3 hours' '+%Y-%m-%dT%H:%M:%SZ')

# 2. Обновить .env на сервере
ssh deploy@80.85.84.156 "
  sed -i 's/^DJANGO_MAINTENANCE_MODE=.*/DJANGO_MAINTENANCE_MODE=True/' /srv/culineire/shared/.env

  grep -q '^DJANGO_MAINTENANCE_UNTIL=' /srv/culineire/shared/.env && \
    sed -i \"s|^DJANGO_MAINTENANCE_UNTIL=.*|DJANGO_MAINTENANCE_UNTIL=${UNTIL}|\" /srv/culineire/shared/.env || \
    echo \"DJANGO_MAINTENANCE_UNTIL=${UNTIL}\" >> /srv/culineire/shared/.env

  grep 'MAINTENANCE' /srv/culineire/shared/.env
"

# 3. Перезапустить Unit
ssh deploy@80.85.84.156 'sudo systemctl restart unit && sleep 2 && sudo systemctl is-active unit'
```

---

## ВЫКЛЮЧИТЬ maintenance

```bash
ssh deploy@80.85.84.156 "
  sed -i 's/^DJANGO_MAINTENANCE_MODE=.*/DJANGO_MAINTENANCE_MODE=False/' /srv/culineire/shared/.env
  sed -i 's|^DJANGO_MAINTENANCE_UNTIL=.*|DJANGO_MAINTENANCE_UNTIL=|' /srv/culineire/shared/.env
  grep 'MAINTENANCE' /srv/culineire/shared/.env
"
ssh deploy@80.85.84.156 'sudo systemctl restart unit && sleep 2 && sudo systemctl is-active unit'
```

---

## Проверить текущий статус

```bash
ssh deploy@80.85.84.156 "grep 'MAINTENANCE' /srv/culineire/shared/.env"
```

---

## Важно

- Всё делается через SSH из Linux VM: `ssh deploy@80.85.84.156`
- `.env` находится в `/srv/culineire/shared/.env` (не в current/)
- После изменения `.env` **обязательно** `sudo systemctl restart unit` — иначе Django не подхватит новые значения
- `DJANGO_MAINTENANCE_UNTIL` — UTC ISO 8601, пример: `2026-05-21T15:30:00Z`
- `/static/`, `/media/`, `/favicon.ico`, `/robots.txt`, `/sitemap.xml`, `/maintenance/notes/` — доступны даже в maintenance
- Greenbear и все модераторы видят 503 как все — нет bypass для залогиненных
