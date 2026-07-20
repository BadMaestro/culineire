---
name: project-arena-hidden-until-release
description: "Арена скрыта от ВСЕХ кроме staff/superuser до официального релиза — это решение владельца, не баг, не спрашивать снова"
metadata: 
  node_type: memory
  type: project
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
  modified: 2026-07-19T18:48:03.173Z
---

**Арена скрыта абсолютно от всех, кто не staff и не superuser, до официального релиза.**
Не только от анонимов — от всех обычных зарегистрированных пользователей тоже.

404 для них — **задумано**. Это НЕ баг, НЕ «сломанный сайт», НЕ повод предлагать
витрину, заглушку «скоро» или превью для незарегистрированных.

`CHEF_BATTLE_ENABLED = False` на проде, в `.env` его нет. Гейт `is_battle_visible`
(`chef_battle/access.py`). Смотреть арену — аккаунтом `CrestedTen` (staff+superuser+
bearseeker, пароль у владельца).

⚠️ **НЕ СПРАШИВАТЬ ОБ ЭТОМ СНОВА.** Владелец 2026-07-19: «постоянно на протяжении
месяцев спрашиваешь меня одно и то же». Наткнулся на 404 в арене — это ответ,
а не вопрос.

Связано: [[project-greenbear-manual-mode]], [[reference-arena-proto-link]].
