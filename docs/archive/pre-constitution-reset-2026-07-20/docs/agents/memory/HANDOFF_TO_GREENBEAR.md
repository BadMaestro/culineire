---
name: handoff-to-greenbear
description: Полный handoff всего контекста следующему разработчику через CoWorking
metadata: 
  node_type: memory
  type: project
  handoff_from: Claude (Sonnet 4.6)
  handoff_to: GreenBear (Next Developer)
  date: 2026-07-10
  status: READY FOR TRANSMISSION
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

# 🤝 ПОЛНЫЙ HANDOFF — CLAUDE → GREENBEAR

## КАК ПРОЧИТАТЬ ЭТУ ИНФОРМАЦИЮ

**ВСЯ ИНФОРМАЦИЯ НАХОДИТСЯ В MEMORY ФАЙЛАХ:**

```
~/.claude/projects/E--CulinEire-Project-CulinEire-CulinEire/memory/
├── MASTER_WORKFLOW.md                          ← НАЧНИ С ЭТОГО (точные команды SSH/deploy)
├── chef_battle_complete_specification.md        ← 7 фаз, все модели, сервисы (3500+ строк)
├── chef_battle_business_model.md                ← 4-сторонний marketplace, retention (1500+ строк)
├── chef_battle_arena_real_mechanic.md           ← Текущий фокус: "Combat is NOT violence" (2000+ строк)
├── chef_battle_legal_compliance.md              ← Stripe, VAT, DAC7, 18+ (1000+ строк)
├── reference_journal_locations.md               ← Все журналы через код/SSH (не браузер)
└── MEMORY.md                                    ← Этот индекс
```

---

## СИНХРОНИЗАЦИЯ С COWORKING

**Команда для синхронизации на production сервере (запусти один раз):**

```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'cd /srv/culineire/current && python manage.py shell' << 'EOF'
import json
from coworking.models import CoworkingSharedMemory, CoworkingAgent
from django.utils import timezone

shared = CoworkingSharedMemory.load()
shared.state_json = {
    "handoff_date": "2026-07-10",
    "from_developer": "Claude",
    "to_developer": "GreenBear",
    "context": "All information synced to ~/.claude/projects/.../memory/ files",
    "status": "Complete — ready to continue",
    "current_version": "v2.5.171",
    "phase_1_status": "MVP Battle Core in production",
    "remaining_work": 3
}
shared.save()

claude = CoworkingAgent.objects.get(agent_id='claude')
greenbear = CoworkingAgent.objects.get(agent_id='greenbear')

claude.status = CoworkingAgent.Status.IDLE
claude.save()
claude.log_entries.create(action='Handoff to GreenBear', result='ok', note='v2.5.171 deployed, 3 items remain')

greenbear.status = CoworkingAgent.Status.ACTIVE
greenbear.save()
greenbear.log_entries.create(action='Received from Claude', result='ok', note='Context in memory files')

print('HANDOFF SYNCED TO COWORKING')
EOF
"
```

---

## 🔴 КРИТИЧНОЕ ПРАВИЛО ПАМЯТИ (ПРОЧИТАЙ ПЕРВЫМ!)

**ЗОЛОТОЕ ПРАВИЛО ПЕРЕДАЧИ:**

1. ✅ **СКОПИРУЙ ВСЕ 6 ФАЙЛОВ ПАМЯТИ СЕБЕ — НЕМЕДЛЕННО**
   - Они более ценны чем любой commit
   - Потеря памяти = потеря месяца работы
   - Каждая новая сессия начинается с их чтения (4 минуты = 100% контекст)

2. ✅ **ЗАПОМНИ НА ВСЕГДА**
   - При каждом начале сессии:
     - Читай `MASTER_WORKFLOW.md` (2 мин)
     - Читай `HANDOFF_TO_GREENBEAR.md` (2 мин)
   - Готово — ты знаешь ТО ЖЕ что я

3. ✅ **НИКОГДА НЕ ТЕРЯЙ КОНТЕКСТ**
   - Когда контекст сжимается (conversation compress)
   - Просто прочитай 4 минуты памяти
   - И ты опять 100% включён в проект

4. ✅ **ОБНОВЛЯЙ НЕМЕДЛЕННО**
   - Версия меняется? → Обнови память
   - Статус меняется? → Обнови память
   - Команда меняется? → Обнови память
   - Не откладывай на "потом"

5. ✅ **ПЕРЕДАВАЙ ТОЧНО КАК ПОЛУЧИЛ**
   - Когда будешь передавать другому:
   - Все 6 файлов
   - Со всеми деталями
   - Никакого сокращения

---

## БЫСТРЫЙ СТАРТ ДЛЯ GREENBEAR

### 1️⃣ ПРОЧИТАЙ СНАЧАЛА (ОДНА ЗА ДРУГОЙ)
```
1. memory/MASTER_WORKFLOW.md (2 мин) — точные команды, текущий статус
2. memory/HANDOFF_TO_GREENBEAR.md (3 мин) — быстрый старт для тебя
3. memory/chef_battle_complete_specification.md — полная спецификация 7 фаз
4. memory/reference_journal_locations.md — как обращаться к журналам через код
```

### 2️⃣ ПОМНИ ЗОЛОТОЕ ПРАВИЛО
```
Ты главный разработчик этого сайта.
✓ Обеспечиваешь себе всё через код
✓ SSH + Django shell для всего
✓ CoWorking для координации
✓ НЕ браузер для журналов
✓ Если чего-то нет → спрашиваешь, не придумываешь
```

### 3️⃣ ТЕКУЩЕЕ СОСТОЯНИЕ (v2.5.171)
- ✅ Phase 1 MVP Battle Core in production
- ✅ ArenaMasterActionSecurityTests 35/35 passing
- ✅ AMC compliance audit #1 complete (audit trail + idempotency keys)
- ⏳ 3 items remaining:
  - Granular security checklist (instead of single boolean)
  - Bulk-load N+1 optimization (P02–P05)
  - Missing combat metrics (P04: misses/defended/surviving)

### 4️⃣ ARENA VISUALIZATION TASK (CURRENT FOCUS)
```
Principle: "Combat is NOT violence" — it's ingredient strategy

Real mechanic:
1. Chefs lock 2 ingredients
2. Biathlon: 3 blind shots at opponent's unlocked ingredients
3. Surviving ingredients get cooked + photographed
4. Moderator verifies
5. Public votes
6. Winner gets Crown 24h

Current implementation task (see chef_battle_arena_real_mechanic.md):
- Port click-ripple to arena-cell
- Fix green in blast-ring
- Surface real Crown holder
- Wire blast-ring to win events
- Curate EPIC/LEGENDARY artifact names (Irish mythology + kitchen)
```

---

## ЖУРНАЛЫ — КАК К НИМ ОБРАЩАТЬСЯ

**Читай memory/reference_journal_locations.md для подробных путей. Вот быстрая справка:**

| Журнал | Как читать |
|--------|-----------|
| **Arena Master Console Plan** | `ssh ... 'ls /srv/culineire/current/docs/chef_battle/arena_master_console/'` |
| **Deployment Journal** | `ssh ... 'cd /srv/culineire/current && git log --oneline -20'` |
| **Battlefield Progress** | `ssh ... 'cd /srv/culineire/current && python manage.py shell' << manage shell script` |
| **CoWorking** | `ssh ... 'cd /srv/culineire/current && python manage.py shell' << read CoworkingSharedMemory` |

---

## EXACT COMMANDS (VERIFIED 2026-07-10)

**SSH (повтор из MASTER_WORKFLOW):**
```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'command'"
```

**Deploy:**
```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'bash /srv/culineire/scripts/deploy.sh 2>&1'"
```

**Git workflow:**
```bash
# 1. Make changes
# 2. Commit with heredoc (English message + Co-Authored-By)
git commit -m "$(cat <<'EOF'
v2.5.X — feature description

- Bullet point

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
# 3. Push
git push origin main
# 4. Deploy runs automatically
```

**Version bump:**
```bash
# Edit: templates/base.html footer-version
# Increment: v2.5.170 → v2.5.171
# Commit + push → auto-deploy
```

---

## CRITICAL RULES

🚫 **NEVER TOUCH:**
- GreenBear page (`/recipes/author/greenbear/`)
- `static/css/god_mode.css`
- Hero layout specs (object-position: center 60%, locked values)

✅ **ALWAYS:**
- Work in `main` branch (not worktree branches)
- Commit → Push → Deploy (autonomous, no permission needed)
- Bump version before deploy
- Run `python manage.py check` before commit
- Read CLAUDE.md for locked rules

✅ **COMMUNICATE:**
- Russian with user, English for code
- CoWorking for handoff/coordination
- Memory files for context preservation

---

## REMAINING WORK (3 items, Priority Order)

### 1. Granular Security Checklist (P05)
Instead of `Recipe.security_checklist` single boolean → add proper checklist model
- Scope: Small (model + migration + tests)
- Files: `recipes/models.py`, `recipes/migrations/`, `recipes/tests.py`

### 2. Bulk-Load N+1 Optimization (P02–P05)
Replace N+1 queries in arena console with `.select_related()` / `.prefetch_related()`
- Scope: Medium (audit + optimization across 4 phases)
- Files: `chef_battle/views.py`, `chef_battle/selectors.py`

### 3. Combat Metrics (P04)
Add missing fields to combat log: `misses`, `defended`, `surviving_ingredients`
- Scope: Medium (model changes + queries + UI)
- Files: `chef_battle/models.py`, `chef_battle/services.py`

---

## MEMORY FILES AT-A-GLANCE

| File | Lines | Contains |
|------|-------|----------|
| `MASTER_WORKFLOW.md` | 200 | SSH commands, deploy, git, version, current state, handoff |
| `chef_battle_complete_specification.md` | 3500 | 7 phases, all models, selectors, services, rules, history |
| `chef_battle_business_model.md` | 1500 | 4-sided marketplace, retention loops, monetization, KPIs |
| `chef_battle_arena_real_mechanic.md` | 2000 | "Combat is NOT violence", arena visualization, artifacts |
| `chef_battle_legal_compliance.md` | 1000 | Company, Stripe, VAT, DAC7, 18+, sponsored battles |
| `reference_journal_locations.md` | 800 | Exact paths to all journals, how to read via code/SSH |
| `HANDOFF_TO_GREENBEAR.md` | 300 | THIS FILE — quick start for next developer |

**Total:** ~9000 lines of documented context

---

## CHECK-IN CHECKLIST

Before starting work, verify:

```bash
# 1. Memory files are synced
ls ~/.claude/projects/E--CulinEire-Project-CulinEire-CulinEire/memory/

# 2. Current version matches
cd "E:\CulinEire Project\CulinEire\CulinEire"
grep -o "v2\.5\.[0-9]*" templates/base.html

# 3. Server is reachable
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode root@80.85.84.156 'echo OK'"

# 4. CoWorking agent status
ssh ... 'cd /srv/culineire/current && python manage.py shell' << check agents

# 5. Read MASTER_WORKFLOW for latest state
cat ~/.claude/projects/.../memory/MASTER_WORKFLOW.md
```

---

## GOOD LUCK! 🚀

Everything is documented. You have:
- ✅ Complete 7-phase specification
- ✅ Business model and retention strategy
- ✅ Legal/compliance checklist
- ✅ All journal locations (via code)
- ✅ Exact SSH/deploy commands
- ✅ Critical rules and anti-patterns
- ✅ Remaining 3 work items with scope

You are the developer. Provide yourself everything through code.

**Questions? Check memory files. Not found? Ask the owner.**

---

**Handoff prepared by:** Claude (Sonnet 4.6)  
**Date:** 2026-07-10  
**Status:** Ready for transmission to GreenBear via CoWorking  
**Next step:** Sync this file to CoWorking shared state, then GreenBear reads from memory/
