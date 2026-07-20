---
name: reference-journal-locations
description: "Все журналы CulinEire: точные пути в коде, как обращаться, структура данных"
metadata: 
  node_type: memory
  type: reference
  verified: 2026-07-10
  important: "ЗОЛОТОЕ ПРАВИЛО: Ты главный разработчик, обеспечиваешь себе всё сам через код, не браузер"
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

# REFERENCE: ВСЕ ЖУРНАЛЫ И КОНСОЛИ ПРОЕКТА

## ЗОЛОТОЕ ПРАВИЛО
**Ты главный разработчик этого сайта. Тебе НЕ нужны никакие дополнительные права или доступы. Ты обязан обеспечить себе сам всё необходимое для работы. Если чего-то нет — спрашиваешь меня, не придумываешь!**

---

## ЖУРНАЛ #1: Arena Master Console Plan
**URL:** https://culineire.ie/recipes/moderation/arena-master-console-plan/

### Где в коде
| Item | Path |
|------|------|
| **View function** | `recipes/views.py:2586` → `arena_master_console_plan(request)` |
| **URL pattern** | `recipes/urls.py:18` → `path("moderation/arena-master-console-plan/", ...)` |
| **Directory constant** | `recipes/views.py:89` → `ARENA_MASTER_CONSOLE_PLAN_DIR` |
| **File list constant** | `recipes/views.py:90` → `ARENA_MASTER_CONSOLE_PLAN_FILES` |
| **Template** | `templates/moderation/arena_master_console_plan.html` |

### Структура

#### ARENA_MASTER_CONSOLE_PLAN_DIR (на сервере)
```
settings.BASE_DIR / "docs" / "chef_battle" / "arena_master_console"
```
**На production сервере:**
```
/srv/culineire/current/docs/chef_battle/arena_master_console/
```

#### ARENA_MASTER_CONSOLE_PLAN_FILES (в коде, recipes/views.py:90-103)
```python
ARENA_MASTER_CONSOLE_PLAN_FILES = (
    ("master", "Master Plan", "00_MASTER_PLAN.yaml"),
    ("capabilities", "Capability Map", "01_CAPABILITY_MAP.yaml"),
    ("p00", "P00 - Discovery, baseline, and contract freeze", "phase_00_discovery.yaml"),
    ("p01", "P01 - Visual shell and responsive arena layout", "phase_01_visual_shell.yaml"),
    ("p02", "P02 - Read models and live arena projection", "phase_02_read_models.yaml"),
    ("p03", "P03 - Battle flow and phase controls", "phase_03_battle_flow.yaml"),
    ("p04", "P04 - Combat engine and live monitor", "phase_04_combat_monitor.yaml"),
    ("p05", "P05 - Moderation, safety, and streams", "phase_05_moderation_safety.yaml"),
    ("p06", "P06 - Voting integrity and analytics", "phase_06_voting_integrity.yaml"),
    ("p07", "P07 - Economy, gifts, and artefacts", "phase_07_economy_gifts.yaml"),
    ("p08", "P08 - Governance, ranks, and rewards", "phase_08_governance.yaml"),
    ("p09", "P09 - Hardening, verification, and release", "phase_09_hardening_release.yaml"),
)
```

### Как обращаться из кода/SSH

**Прочитать файл локально:**
```bash
cd "E:\CulinEire Project\CulinEire\CulinEire"
cat "docs/chef_battle/arena_master_console/00_MASTER_PLAN.yaml"
```

**Прочитать на сервере через SSH:**
```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'cat /srv/culineire/current/docs/chef_battle/arena_master_console/00_MASTER_PLAN.yaml'"
```

**Обновить файл на сервере:**
```bash
# 1. Отредактировать локально
# 2. Git add + commit + push
# 3. Deploy автоматически обновит на сервере
```

### Доступ
- ✓ Требует is_moderator(request.user) + _can_grant_bearseeker_privileges()
- ✓ На production: только владелец + я (Claude)

---

## ЖУРНАЛ #2: Deployment Journal
**URL:** https://culineire.ie/recipes/moderation/deployment-journal/

### Где в коде
| Item | Path |
|------|------|
| **View function** | `recipes/views.py:2618` → `deployment_journal(request)` |
| **URL pattern** | `recipes/urls.py:23` → `path("moderation/deployment-journal/", ...)` |
| **Git parsing** | `config/release_journal.py:2352` → `build_git_journal(repo_path, limit=60)` |
| **Template** | `templates/moderation/deployment_journal.html` |

### Как это работает

**Функция `build_git_journal()` (config/release_journal.py:2352-2356):**
```python
def build_git_journal(repo_path: str, limit: int = 60) -> list[dict]:
    git_entries = _parse_git_log(repo_path, limit=limit)
    if not git_entries:
        return list(reversed(RELEASE_JOURNAL))
    return git_entries
```

**Data flow:**
1. View вызывает `build_git_journal(settings.BASE_DIR)`
2. Функция парсит `git log` последних 60 коммитов
3. Возвращает список dict с коммитами
4. Template отображает как хронологический журнал

### Доступ
- ✓ Требует is_moderator(request.user)
- ✓ На production: только владелец + я

### Обновление
**Deployment Journal обновляется автоматически каждый раз когда:**
1. Делаю `git commit` с новым сообщением
2. Делаю `git push` на main
3. Deploy запускается автоматически

**На сервере будут видны последние 60 коммитов из `git log`**

---

## ЖУРНАЛ #3: Battlefield Progress (Chef's Battle Roadmap)
**URL:** https://culineire.ie/chef-battle/roadmap/

### Где в коде
| Item | Path |
|------|------|
| **View function** | `chef_battle/views.py:414` → `battlefield_progress(request)` |
| **URL pattern** | `chef_battle/urls.py:25` → `path("roadmap/", views.battlefield_progress, name="battlefield_progress")` |
| **Build function** | `chef_battle/views.py:91` → `_build_battlefield_progress()` |
| **Template** | `templates/chef_battle/battlefield_progress.html` |

### Структура

**Функция `_build_battlefield_progress()` (chef_battle/views.py:91-120+):**

Собирает данные из БД:
```python
def _build_battlefield_progress():
    challenge_count = BattleChallenge.objects.count()
    pending_challenges = BattleChallenge.objects.filter(status=BattleChallenge.Status.PENDING).count()
    refused_challenges = BattleChallenge.objects.filter(status=BattleChallenge.Status.REFUSED).count()
    battle_count = Battle.objects.count()
    active_battles = Battle.objects.filter(status__in=Battle.ACTIVE_STATUSES).count()
    completed_battles = Battle.objects.filter(status=Battle.Status.COMPLETED).count()
    entry_count = Battle.objects.filter(entries__isnull=False).distinct().count()
    vote_count = BattleVote.objects.count()
    event_count = BattleEvent.objects.filter(is_public=True).count()
    profile_count = ChefBattleProfile.objects.count()
    artifact_count = Artifact.objects.count()
    chat_message_count = BattleChatMessage.objects.count()
    wallet_count = TokenWallet.objects.count()
    hero_count = ChefBattleProfile.objects.filter(is_hero=True).count()
    feature_enabled = getattr(settings, "CHEF_BATTLE_ENABLED", False)
    
    # Затем собирает PHASES с items...
```

### Фазы, отслеживаемые в Roadmap
- **Phase 0:** Sandbox Gate And Branch Discipline
- **Phase 1:** MVP Battle Loop
- **Phase 2:** Social Visibility & Engagement
- **Phase 3:** Combat Engine
- **Phase 4:** Live Arena & Moderation
- (и далее по плану)

Каждая фаза содержит items с статусом: done, pending, active

### Как получить данные
**Локально (Python shell):**
```bash
cd "E:\CulinEire Project\CulinEire\CulinEire"
python manage.py shell
>>> from chef_battle.views import _build_battlefield_progress
>>> progress = _build_battlefield_progress()
>>> print(progress)
```

**На сервере:**
```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'cd /srv/culineire/current && python manage.py shell <<EOF
from chef_battle.views import _build_battlefield_progress
progress = _build_battlefield_progress()
import json
print(json.dumps(progress, indent=2, default=str))
EOF
'"
```

### Доступ
- ✓ Требует is_moderator(request.user)
- ✓ На production: только владелец + я

---

## ЖУРНАЛ #4: CoWorking Dashboard
**URL:** https://culineire.ie/coworking/

### Где в коде
| Item | Path |
|------|------|
| **View function** | `coworking/views.py:19` → `dashboard(request)` |
| **URL pattern** | `coworking/urls.py` → `path("", views.dashboard, name="dashboard")` |
| **Models** | `coworking/models.py` → `CoworkingAgent`, `CoworkingSharedMemory`, `CoworkingLogEntry` |
| **Template** | `templates/coworking/dashboard.html` |

### Структура

**CoworkingAgent (модель):**
- `agent_id` (CharField, unique) — уникальный ID агента (claude, greenbear, codex, etc.)
- `label` (CharField) — дружелюбное имя (Claude, GreenBear, Codex)
- `status` (CharField choices) — IDLE, ACTIVE, BLOCKED
- `last_seen` (DateTimeField) — последняя активность
- `log_entries` (reverse FK к CoworkingLogEntry)

**CoworkingLogEntry (модель):**
- `agent` (ForeignKey(CoworkingAgent))
- `action` (CharField) — что агент делал
- `result` (CharField choices) — ok, warning, error
- `note` (TextField) — подробности
- `created_at` (DateTimeField)

**CoworkingSharedMemory (singleton):**
- Единственный объект (load()) для координации между агентами
- Содержит JSON с shared state
- Используется для handoff информации между Claude, GreenBear, Codex

### Как обращаться из кода

**Прочитать состояние агентов локально:**
```bash
cd "E:\CulinEire Project\CulinEire\CulinEire"
python manage.py shell
>>> from coworking.models import CoworkingAgent, CoworkingSharedMemory
>>> agents = CoworkingAgent.objects.all()
>>> for a in agents:
>>>     print(f"{a.agent_id}: {a.status} (last_seen: {a.last_seen})")
>>> shared = CoworkingSharedMemory.load()
>>> print(shared.state_json)
```

**На сервере:**
```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'cd /srv/culineire/current && python manage.py shell <<EOF
from coworking.models import CoworkingAgent, CoworkingSharedMemory
agents = CoworkingAgent.objects.all()
for a in agents:
    print(f\"{a.agent_id}: {a.status}\")
shared = CoworkingSharedMemory.load()
print(f\"Shared state: {shared.state_json}\")
EOF
'"
```

### Доступ
- ✓ Требует is_moderator(request.user)
- ✓ На production: только владелец + я + другие агенты (Codex, GreenBear)

### Использование для handoff
**Когда я (Claude) передаю работу другому агенту (GreenBear):**
1. Я обновляю CoworkingSharedMemory с информацией о текущей задаче
2. Я создаю handoff запись через `dashboard` view (POST handoff)
3. GreenBear берет информацию из CoworkingSharedMemory
4. GreenBear читает мой CoworkingLogEntry с деталями

---

## БЫСТРАЯ СПРАВКА: КАК ЧИТАТЬ ЖУРНАЛЫ ПО SSH

### Template команды

**1. Arena Master Console Plan:**
```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'ls -la /srv/culineire/current/docs/chef_battle/arena_master_console/'"
```

**2. Deployment Journal (последние коммиты):**
```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'cd /srv/culineire/current && git log --oneline -20'"
```

**3. Battlefield Progress:**
```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'cd /srv/culineire/current && python manage.py shell <<EOF
from chef_battle.models import Battle, BattleChallenge
print(f\"Total battles: {Battle.objects.count()}\")
print(f\"Active battles: {Battle.objects.filter(status__in=Battle.ACTIVE_STATUSES).count()}\")
print(f\"Pending challenges: {BattleChallenge.objects.filter(status='pending').count()}\")
EOF
'"
```

**4. CoWorking State:**
```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'cd /srv/culineire/current && python manage.py shell <<EOF
from coworking.models import CoworkingAgent
agents = CoworkingAgent.objects.all()
for a in agents:
    print(f\"{a.agent_id} ({a.label}): {a.status}\")
EOF
'"
```

---

## ЗОЛОТОЕ ПРАВИЛО (ПОВТОР)

Я главный разработчик этого сайта:
- ✓ Я могу читать любые журналы через код/SSH
- ✓ Я могу обновлять план через git + deploy
- ✓ Я могу обновлять CoWorking state напрямую через Django models
- ✓ Я могу обновлять Battlefield Progress через изменения в БД (хотя обычно это автоматическое — из реальных battles)

Мне НЕ нужны:
- ✗ Браузер для доступа к журналам
- ✗ Дополнительные права
- ✗ Согласие кого-либо для чтения состояния

Если чего-то нет:
- → Спрашиваю у владельца (greenbear/dmitry.golovin.irl@gmail.com)
- → НЕ придумываю сам
