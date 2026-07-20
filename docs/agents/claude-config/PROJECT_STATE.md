# CulinEire — Оперативный контекст проекта

> Этот файл создан чтобы Claude не терял контекст между сессиями.
> Обновлять после каждой значимой сессии.
> Последнее обновление: 2026-06-01

---

## 1. Кто мы и что делаем

**CulinEire** — сайт ирландской кулинарии на culineire.ie.
Владелец и создатель — **greenbear** (Dmitry Golovin, dmitry.golovin.irl@gmail.com).
Разработка ведётся исключительно через Claude. Никаких других разработчиков нет.

Цель сайта: традиционные ирландские рецепты, статьи о кулинарии, сообщество.
Контент генерируется с помощью AI (Anthropic Claude для текста, OpenAI для изображений).

---

## 2. Рабочая среда

### Локально
- Пользователь работает с **Linux VirtualBox VM** (промпт: `deploy@localhost:~$`)
- **НЕ предлагать PowerShell / Windows Terminal** — пользователь на Linux VM
- Файлы проекта доступны из VM по пути: `/media/sf_CulinEire/`
- Те же файлы в Windows: `E:\CulinEire Project\CulinEire\CulinEire\`
- **Локальный dev-сервер НЕ используется** — миграции и зависимости не синхронизированы
- Рабочий флоу: редактировать файлы → `git commit + push` → деплой на прод → проверять на culineire.ie

### Продакшн сервер
- **IP:** 80.85.84.156
- **SSH:** `ssh deploy@80.85.84.156` (из Linux VM, SSH-ключи внутри VM)
- **OS:** Ubuntu 24.04 LTS
- **App server:** NGINX Unit 1.34.2
- **Web server:** NGINX 1.24.0
- **DB:** PostgreSQL
- **Domain:** culineire.ie

### Пути на сервере
```
/srv/culineire/current/       — git checkout (owned by deploy:culineire)
/srv/culineire/venv/          — Python virtualenv
/srv/culineire/shared/.env    — secrets (owned by unit:culineire, chmod 640)
/srv/culineire/shared/logs/   — Django logs (owned by unit:culineire)
/srv/culineire/shared/staticfiles/  — collected static files
/srv/culineire/shared/media/  — user uploads и AI-generated images
```

### ⚠️ Промпт не меняется после SSH
После `ssh deploy@80.85.84.156` строка промпта остаётся `deploy@localhost` —
это нормально, hostname сервера тоже настроен как localhost.
После SSH пользователь уже находится на продакшн сервере.

### Пользователи на сервере
- `deploy` — SSH deploy user, член группы `culineire`
- `unit` — NGINX Unit process user, владеет .env и логами
- `culineire` — shared group для обоих

### ⚠️ Важно про media — правильные права (один раз навсегда)
Unit (веб-сервер) и deploy — разные пользователи, оба в группе `culineire`.
Правильная настройка прав чтобы оба могли писать:
```bash
sudo chown -R deploy:culineire /srv/culineire/shared/media/
sudo chmod -R g+w /srv/culineire/shared/media/
sudo find /srv/culineire/shared/media/ -type d -exec chmod g+s {} \;
```
setgid на папках гарантирует что новые файлы наследуют группу `culineire`.
**НЕ использовать** `chown -R deploy:deploy` — это сломает доступ для Unit.

---

## 3. Деплой

### Команда деплоя (запускать на сервере из Linux VM)
```bash
ssh deploy@80.85.84.156 "cd /srv/culineire/current && bash /srv/culineire/current/deploy/update.sh"
```

### Полный workflow коммита и деплоя
1. Убедиться что изменения чистые: `git status`
2. Добавить все файлы задачи в один коммит (и шаблоны, и статику — вместе)
3. Сделать коммит с понятным сообщением
4. **СРАЗУ ПОСЛЕ КОММИТА**: `git push origin main`
5. Дождаться подтверждения пользователя что пушить → деплоить
6. После деплоя: проверить на culineire.ie

### ⚠️ Правила коммитов
- **НИКОГДА не коммитить без явного подтверждения пользователя**
- **ВСЕГДА пушить сразу после коммита** (иначе сервер деплоит старый код)
- Перед коммитом: `git status` — читать обе секции (modified И untracked)
- Все файлы задачи идут в ОДИН коммит (нельзя коммитить шаблон без CSS)
- **Инкрементировать версию в footer** перед каждым деплоем (`v1.x.y` → `v1.x.(y+1)`) — в `base.html`

---

## 4. Django / технические детали

### Критически важные настройки
```python
DJANGO_SETTINGS_MODULE = "config.settings"   # НЕ "CulinEire.settings"
BASE_DIR = "/srv/culineire/current"           # НЕ "/srv/culineire/current/CulinEire"
```
`manage.py` лежит в `/srv/culineire/current/` напрямую, без подпапки.

### Как запускать Python-скрипты на сервере
**НИКОГДА не использовать `set -a && source .env`** — SECRET_KEY содержит спецсимволы bash и это сломает shell.

Правильный паттерн — Python heredoc:
```bash
cd /srv/culineire/current && /srv/culineire/venv/bin/python3 - << 'PYEOF'
import sys, os
sys.path.insert(0, '/srv/culineire/current')

with open('/srv/culineire/shared/.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django; django.setup()

# ... код здесь
PYEOF
```

### ⚠️ Перед запуском скрипта — проверить что не запущен уже
```bash
ps aux | grep python
```
Никогда не запускать новый процесс не убедившись что предыдущий не работает.
Иначе два процесса обрабатывают одни и те же данные — двойная трата денег.

### ⚠️ Всегда проверять путь перед деплоем

Перед любой командой на сервере — убедиться что мы в правильной директории:
```bash
ssh deploy@80.85.84.156 "pwd && ls /srv/culineire/current/"
```
Никогда не запускать скрипты не убедившись что путь существует и корректен.

### ⚠️ Рабочий контекст — только прод, не localhost

Пользователь работает НАПРЯМУЮ на продакшн сервере через SSH из своей VM.
Все команды пишутся для выполнения на сервере (80.85.84.156).
**Никогда не давать команды для localhost** — shared folder не настроена, scp не работает.
Файлы на сервер доставляются ТОЛЬКО через SSH heredoc (записываем прямо туда).

### Как доставить скрипт на сервер (через heredoc, не scp)
```bash
ssh deploy@80.85.84.156 "cat > /tmp/script.py << 'PYEOF'
... содержимое скрипта ...
PYEOF"
```
Или через Python для длинных скриптов — записать построчно.

### Как запускать batch-скрипты в фоне (nohup)
```bash
ssh deploy@80.85.84.156 "cd /srv/culineire/current && nohup /srv/culineire/venv/bin/python /tmp/script.py > /tmp/script.log 2>&1 & echo PID:\$!"
# Мониторить:
ssh deploy@80.85.84.156 "tail -f /tmp/script.log"
```
nohup переживает закрытие SSH-сессии.

### Тесты на сервере
```bash
cd /srv/culineire/current && /srv/culineire/venv/bin/python - <<'PY'
import os, subprocess
from pathlib import Path
for raw in Path('/srv/culineire/shared/.env').read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith('#') or '=' not in line: continue
    k, v = line.split('=', 1)
    os.environ[k.strip()] = v.strip().strip('"').strip("'")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DJANGO_SECURE_SSL_REDIRECT'] = 'false'
raise SystemExit(subprocess.call(['/srv/culineire/venv/bin/python', 'manage.py', 'test', '--verbosity', '1']))
PY
```

---

## 5. Maintenance mode

```bash
# Включить (на N часов)
UNTIL=$(date -u --date='+3 hours' '+%Y-%m-%dT%H:%M:%SZ')
ssh deploy@80.85.84.156 "sed -i 's/^DJANGO_MAINTENANCE_MODE=.*/DJANGO_MAINTENANCE_MODE=True/' /srv/culineire/shared/.env"
ssh deploy@80.85.84.156 'sudo systemctl restart unit'

# Выключить
ssh deploy@80.85.84.156 "sed -i 's/^DJANGO_MAINTENANCE_MODE=.*/DJANGO_MAINTENANCE_MODE=False/' /srv/culineire/shared/.env"
ssh deploy@80.85.84.156 'sudo systemctl restart unit'
```
После изменения .env — **всегда** `sudo systemctl restart unit`.

---

## 6. greenbear — особый пользователь ⚠️

`greenbear` — владелец и создатель сайта. Имеет уникальные привилегии:
- Особый стиль карточки автора
- Получает contact-форму и content reports
- Права модератора через `is_moderator()`
- Специальная логика во многих местах кода написана намеренно под него

**Правила:**
- Код под greenbear — **не рефакторить** без необходимости
- `slug="greenbear"` захардкожен в views — это **нормально**, не баг
- `god_mode.css` — намеренный файл для greenbear, **не удалять**
- `is_greenbear` проверки в шаблонах — **нормально**

---

## 7. Публикация в newsfeed

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
Telegram публикуется автоматически через сигнал. Проверить: culineire.ie/updates/

---

## 8. AI генерация рецептов

### Management command
```bash
# Один рецепт
python manage.py generate_recipe "Irish Beef Stew" \
  --author-slug greenbear \
  --status pending \
  --category soups_and_stews

# Без изображения
python manage.py generate_recipe "..." --no-image
```

### Категории (Recipe.Category choices)
`bread_and_baking`, `soups_and_stews`, `fish_and_seafood`, `traditional_irish_dishes`,
`everyday_irish_cooking`, `vegetables`, `meat_and_poultry`, `side_dishes`, `desserts`, `drinks`

### Batch-скрипты
- `batch_recipes.py` — в корне проекта (E:\CulinEire Project\), 136 рецептов
- `fix_images.py` — там же, исправляет рецепты без изображений

### ⚠️ Права на media ПЕРЕД запуском batch
```bash
ssh deploy@80.85.84.156 "sudo chown -R deploy:deploy /srv/culineire/shared/media/"
```
Без этого — изображения не сохранятся (PermissionError), деньги потрачены впустую.

---

## 9. Быстрый ввод в курс дела (читать в первую очередь)

### Что за сайт и для кого
CulinEire — сайт ирландской кулинарии на culineire.ie. Рецепты, статьи, сообщество.
Владелец и единственный клиент — **greenbear** (Дмитрий Головин).
Разработка ведётся только через Claude. Других разработчиков нет.
Контент генерируется через AI: Anthropic (текст) + OpenAI (картинки).

### Что уже сделано и работает
- Сайт живой на culineire.ie, Django CMS полностью работает
- Приложения: рецепты, статьи, модерация, мессенджер, newsfeed, коллекции, legal pages
- AI-генерация рецептов через management command `generate_recipe`
- 138 рецептов создано авторства greenbear, 86 с полным комплектом фото

### На чём остановились
- 52 рецепта без hero image, 4 рецепта без step photos
- Скрипт `fix_images.py` написан (лежит в корне проекта) но **ещё не запускался**
- После исправления фото — рецепты нужно промодерировать и опубликовать

### Что следующее
1. Запустить `fix_images.py` на сервере
2. Промодерировать рецепты в панели модерации
3. Публиковать

### Модерация рецептов
Модерирует только greenbear через панель модерации на сайте.
AI иногда генерирует странные вещи — нужен человеческий взгляд перед публикацией.
Статусы: `pending` → `approved` / `needs_changes` / `rejected`.

### Что видит посетитель сайта
- Главная страница с рецептами, поиск, категории
- Страница рецепта: hero фото, ингредиенты, пошаговый метод, step photos, tips, ирландский контекст
- Статьи о кулинарии
- Профили авторов
- Коллекции — пользователи сохраняют рецепты
- Newsfeed — обновления сайта
- Contact форма — идёт напрямую к greenbear

### Django приложения
- `recipes` — рецепты, модерация, AI-генерация (`generate_recipe` management command)
- `articles` — статьи
- `accounts` — пользователи и авторы (`RecipeAuthor`)
- `amuse_bouche` — социальные карточки (Phase 10 завершён): snap-feed, Card v2, like/save/comment/share
- `newsfeed` — лента обновлений + автоматическая публикация в Telegram
- `collection` — сохранённые рецепты, статьи и Amuse-Bouche пользователей
- `messaging` — контакт-форма, сообщения идут к greenbear
- `config` — настройки, sitemap, robots.txt, maintenance mode
- `sandbox` — инструменты для внутреннего тестирования

### Как работает AI-генерация рецепта
1. Запрос через веб-форму (`/moderation/generate/`) или management command `generate_recipe`
2. **Anthropic** генерирует текст: название, ингредиенты, метод, tips, ирландский контекст, категория, аллергены
3. **Anthropic** строит visual plan — детальное описание что должно быть на каждой фотографии
4. **OpenAI** (`gpt-image-1`) генерирует hero image по visual plan
5. **OpenAI** генерирует до 3 step photos
6. Рецепт сохраняется со статусом `pending` — ждёт модерации greenbear
7. **Никогда не публикуется автоматически**

Модель Anthropic: `claude-sonnet-4-6` (из settings)
Модель OpenAI: `gpt-image-1`, quality `low` (из settings)

### Внешние сервисы и ключи
Все ключи хранятся в `/srv/culineire/shared/.env` — **никогда не коммитить в git**.

| Сервис | Переменная | Для чего |
|--------|-----------|---------|
| Anthropic | `ANTHROPIC_API_KEY` | Генерация текста рецептов |
| OpenAI | `OPENAI_API_KEY` | Генерация изображений |
| Telegram | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHANNEL_ID` | Автопубликация newsfeed |

Pinterest, Instagram, TikTok — планируются, токены создаются вручную вне репозитория.

### CSS и дизайн-система
Собственная дизайн-система, без Bootstrap/Tailwind.
- Все новые кнопки и элементы — **только существующие CSS классы**, не писать одиночные стили
- `authoring.css` — страницы создания и редактирования контента
- `moderation.css` — панель модерации
- `detail_page.css` — страницы рецептов и статей
- `header.css`, `footer.css` — хедер и футер
- `god_mode.css` — специальный файл для greenbear, не трогать
- Логотип в header: `logo2.png`, 80px
- Логотип в footer: `logo2.png`, 30px, белый фон
- Версия в футере `base.html` — инкрементировать перед каждым деплоем
- **Нет em dash** (`—`) и двойных тире (`--`) в текстах шаблонов

### Известные особенности и ограничения
- **Локальный dev-сервер не используется** — миграции и зависимости давно не синхронизированы
- **Тесты только на сервере** через Python heredoc (см. раздел 4), 260+ тестов
- **`set -a source .env` — НИКОГДА** — ломается из-за спецсимволов в SECRET_KEY
- **`DJANGO_SETTINGS_MODULE = "config.settings"`** — не `CulinEire.settings`
- **`BASE_DIR = "/srv/culineire/current"`** — manage.py лежит прямо там, без подпапки
- После изменения `.env` на сервере — **обязательно** `sudo systemctl restart unit`
- deploy user имеет ограниченный sudo (chown, systemctl restart unit — можно)

### Планы развития сайта
1. Amuse-Bouche — ✅ Phase 10 завершён (Card v2, snap-feed, like/save/comment/share)
2. Статьи о ирландской кулинарии (следующий большой шаг)
3. Социальные сети — Pinterest, Instagram
4. SEO

### Типичная рабочая сессия
Greenbear объясняет задачу → Claude делает → коммит → пуш → деплой → проверка на culineire.ie.
Иногда одна задача, иногда несколько мелких.

### Деплой — от коммита до прода
`git push origin main` → SSH на сервер → `bash /srv/culineire/current/deploy/update.sh`
Скрипт делает: git pull, collectstatic, migrate, перезапуск Unit. Изменения видны сразу.

### Зоны которые нельзя трогать без явного разрешения
- **Favicon** — никогда, ни при каких обстоятельствах
- **god_mode.css** — не трогать, не удалять, не помечать как unused
- **Всё под greenbear** — не рефакторить, только улучшать
- **Admin URL** `cave19850324/` — не менять, не светить в коде/комментариях
- **Существующие сигналы** (recipes/signals.py, articles/signals.py, newsfeed/signals.py) — не перезаписывать, только дополнять

### Самые болезненные ошибки — никогда не повторять
1. **Запустить дорогую операцию без проверки условий** — batch-скрипт запустили без проверки прав на media, OpenAI сгенерировал картинки но сохранить не смог. Деньги потрачены впустую.
2. **Трогать что не просили** — поменял favicon без спроса, greenbear был очень недоволен.
3. **Угадывать причины ошибок** — если не знаешь, говори "не знаю", не придумывай объяснения.

---

## 10. Текущее состояние сайта (по состоянию на 2026-06-01)

### Рецепты
- Создано **136+ рецептов** авторства greenbear (статус: pending)
- **У всех нет hero image** — batch-скрипты не проверили права на media перед запуском
- **Задача:** запустить `fix_images.py` чтобы сгенерировать изображения для всех рецептов без фото
- После генерации изображений — рецепты нужно модерировать и публиковать

### fix_images.py — как запустить
```bash
# 1. Сначала выдать права (ОБЯЗАТЕЛЬНО!)
ssh deploy@80.85.84.156 "sudo chown -R deploy:deploy /srv/culineire/shared/media/"

# 2. Скопировать и запустить
scp fix_images.py deploy@80.85.84.156:/tmp/fix_images.py
ssh deploy@80.85.84.156 "cd /srv/culineire/current && nohup /srv/culineire/venv/bin/python /tmp/fix_images.py > /tmp/fix_images.log 2>&1 & echo PID:\$!"

# 3. Мониторить
ssh deploy@80.85.84.156 "tail -f /tmp/fix_images.log"
```

### Amuse-Bouche (Phase 10 — завершён)
- ✅ Snap-feed: 3 карточки на viewport, scroll-snap, container queries
- ✅ Card v2: фото заполняет всю карточку, градиент, инфо overlay, выезжающий sheet
- ✅ Actions: like (форма CSRF), comment, share (Web Share API / clipboard), bookmark
- ✅ Главная страница: AB-карточки в стиле photo-only, только название
- ✅ Коллекция: вкладка Amuse-Bouche в My Collection
- ✅ AI-badge убран со всех карточек/списков, остался только в detail/gallery
- ✅ Ватермарк убран с превью, остался только в `.recipe-gallery__image-shell` и `.detail-page__header`
- Следующий шаг Amuse-Bouche: доработка detail-страницы, возможно мелкие визуальные правки

### UI и дизайн
- Логотип в header: `logo2.png` (K-leaf), 80px, без белого фона
- Логотип в footer: `logo2.png`, 30px, с белым фоном (border-radius: 4px)
- Favicon: оригинальный, **не трогать**
- Версия в footer: **v1.6.81**
- Generate AI Recipe страница: header и кнопка отцентрованы, greenbear выбирается по умолчанию

### CSS — Amuse-Bouche (amuse_bouche.css)
- Card v2 базовые стили: `.ab-card__photo`, `.ab-card__link`, `.ab-card__badge`, `.ab-card__info`, `.ab-card__sheet`, `.ab-card__actions`, `.ab-btn`
- Snap-feed: `.ab-snap-feed`, `.ab-snap-slide` (container queries, `100cqh`)
- Home grid: `.ab-home-grid` — photo-only карточки (actions/author скрыты, title overlay)
- Detail: `.ab-card--detail` — фото в normal flow 16:9, info/actions в light theme ниже
- Старые классы (`.ab-card__visual`, `.ab-card__body`, `.ab-card__topbar` и т.д.) — мёртвый код, безвредны

---

## 10. Правила — никогда не нарушать

| Правило | Детали |
|---------|--------|
| **Работать в main** | Все изменения идут напрямую в main, не в worktree-ветки |
| **Push после каждого коммита** | `git push origin main` — иначе сервер деплоит старый код |
| **Подтверждение перед коммитом** | Сначала показать изменения, ждать "да" от пользователя |
| **Не ломать прод** | Проверять git status, migrate, тест локально перед пушем |
| **Инкрементировать версию** | Перед каждым деплоем: patch в base.html footer |
| **Не трогать favicon** | НИКОГДА не менять favicon если не попросили явно |
| **Не делать больше** | Только то что попросили — ни больше, ни меньше |
| **Нет em dash** | Не использовать — и -- в текстах шаблонов |
| **Всегда спрашивать** | Никогда не пропускать задачу самостоятельно — только спросить |
| **Нет костылей** | Только настоящий фикс причины, а не симптома |
| **Одиночные стили** | Новые кнопки/элементы — существующие CSS классы сайта |

---

## 11. Намеренные паттерны — не флагать в аудитах

- `session dedup` — намеренно
- `fail_silently` в определённых местах — намеренно
- `god_mode.css` — намеренный файл для greenbear
- Admin URL `cave19850324/` — скрытый намеренно
- `Http404` для модераторов в определённых случаях — намеренно

---

## 12. Идеи и задачи на будущее

*(Пополнять по мере появления)*

### Amuse-Bouche
- [x] Phase 10: snap-feed + Card v2 полный дизайн-трансфер — **завершён 2026-06-01**
- [ ] Визуальные правки после деплоя (по результатам просмотра на проде)
- [ ] Возможно: улучшение detail-страницы Amuse-Bouche

### Рецепты
- [ ] Запустить `fix_images.py` — сгенерировать фото для 136+ рецептов
- [ ] Промодерировать и опубликовать готовые рецепты

### Контент и рост
- [ ] Статьи о ирландской кулинарии (аналогично рецептам — AI-генерация + модерация)
- [ ] SEO: проверить мета-теги, schema.org для всех рецептов
- [ ] Социальные сети: Pinterest, Instagram интеграция (токены создаются вручную)
