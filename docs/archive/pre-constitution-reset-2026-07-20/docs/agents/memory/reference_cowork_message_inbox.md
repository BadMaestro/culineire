---
name: reference-cowork-message-inbox
description: CoWork направленные сообщения между агентами (CoworkingMessage) + живой 15-сек поллер инбокса bolt
metadata: 
  node_type: memory
  type: reference
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

С v2.5.191 у CoWork есть **направленные сообщения** между агентами (не только
общий лог). Модель `coworking.models.CoworkingMessage`.

**Отправить сообщение (bolt↔greenbear):**
```python
CoworkingMessage.send(from_agent="greenbear", to_agent="bolt",
                      subject="...", body="...")
```

**Прочитать свой инбокс / пометить прочитанным:**
```python
CoworkingMessage.unread_for("bolt")          # unread, oldest first
python manage.py agent_inbox bolt --unread   # или --since <id>, --mark-read
```

**Живой поллер (механизм A, одобрен владельцем 2026-07-13, интервал 15 сек):**
- Скрипт: `scratchpad/gb_inbox_poller.sh` — каждые 15 сек по SSH зовёт
  `manage.py agent_inbox bolt --since <watermark>`, эхает новые сообщения
  (каждая строка = уведомление в чат), двигает локальный watermark-файл.
- Запуск: инструмент **Monitor**, `persistent: true`. Watermark:
  `scratchpad/gb_inbox_watermark`.
- **Ограничение (честно):** работает ТОЛЬКО пока сессия жива. Между сессиями
  разбудить меня может лишь планировщик владельца (вариант C, не сделан).
- **В начале каждой рабочей сессии:** заново стартовать поллер (Monitor) и
  проверить `agent_inbox bolt --unread`.

**Для GreenBear:** писать мне через `CoworkingMessage.send(to_agent="bolt", ...)`,
а не прятать в note лог-записей. Связано с [[reference-coworking-app]],
[[feedback-log-every-step]], [[project-phase6-split]].
