---
name: post-newsfeed-entry-via-terminal
description: "Как публиковать новости на сайте напрямую через SSH с Linux VM, без UI"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8d5a4c87-817e-4fb0-a645-1e388a00f77d
---

## ЕДИНСТВЕННО РАБОЧИЙ ПАТТЕРН

```bash
cd /srv/culineire/current && /srv/culineire/venv/bin/python3 - << 'PYEOF'
import sys, os
sys.path.insert(0, '/srv/culineire/current')
import dotenv; dotenv.load_dotenv('/srv/culineire/shared/.env')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django; django.setup()
from django.contrib.auth import get_user_model
from newsfeed.models import NewsFeedEntry
from django.utils import timezone
User = get_user_model()
greenbear = User.objects.get(username='greenbear')
e = NewsFeedEntry.objects.create(
    entry_type=NewsFeedEntry.EntryType.SITE_UPDATE,
    title="TITLE HERE",
    message="MESSAGE HERE",
    is_public=True,
    is_auto=False,
    published_at=timezone.now(),
    created_by=greenbear,
)
print(f"Created entry #{e.pk}: {e.title}")
PYEOF
```

## Критически важные детали — нарушение любого пункта = ошибка

1. `cd /srv/culineire/current` — ОБЯЗАТЕЛЬНО перед командой
2. `/srv/culineire/venv/bin/python3` — ТОЛЬКО venv, не системный python/python3
3. `python3 -` с heredoc `<< 'PYEOF'` — читать из stdin, НЕ писать скрипт в /tmp/
4. `sys.path.insert(0, '/srv/culineire/current')` — ПЕРВАЯ строка после импортов
5. `dotenv.load_dotenv(...)` — ДО django.setup()

## Почему /tmp/ не работает
- `python3 /tmp/script.py` добавляет `/tmp` в sys.path, а не `/srv/culineire/current`
- Django не находит модуль `config` → ModuleNotFoundError
- `python3 -` добавляет текущую директорию (cwd) в sys.path → работает

## Почему не set -a / source .env
- SECRET_KEY содержит спецсимволы bash → ломает shell

## Entry types
- `NewsFeedEntry.EntryType.SITE_UPDATE` — обновление/анонс
- `NewsFeedEntry.EntryType.VERSION_RELEASE` — релиз версии
- `NewsFeedEntry.EntryType.SECURITY_UPDATE` — security
- `NewsFeedEntry.EntryType.ADMIN_NOTE` — внутренняя заметка
- `NewsFeedEntry.EntryType.RECIPE_PUBLISHED` — рецепт опубликован
- `NewsFeedEntry.EntryType.ARTICLE_PUBLISHED` — статья опубликована

## Telegram
Публикация в Telegram идёт автоматически через сигнал при создании записи — ничего дополнительно делать не нужно.

## Проверка
После создания: `culineire.ie/updates/`
