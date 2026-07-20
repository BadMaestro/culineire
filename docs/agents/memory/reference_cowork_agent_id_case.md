---
name: reference-cowork-agent-id-case
description: "CoWork agent_id — регистрозависимый PK; 'GreenBear' != 'greenbear' создаёт второй ящик и почта молча теряется"
metadata: 
  node_type: memory
  type: reference
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

`CoworkingMessage.send(to_agent="...")` делает **get_or_create по строке**, а
`agent_id` — регистрозависимый slug-PK. Опечатка в регистре не падает с ошибкой:
она **создаёт новую строку агента**, письмо уходит в неё, отправитель видит
«SENT id=...» и считает, что доставил. Получатель не видит ничего.

**Канонические id — только строчные: `bolt`, `greenbear`, `ember`, `owner`.**
Никогда не использовать `claude` как agent_id (коллизия личности).

**Why:** 2026-07-17 я отправил #378 на `GreenBear` вместо `greenbear`. GB не
получил письмо; я решил, что он молчит; он решил, что я игнорирую его третий
вопрос подряд. Обнаружилось только потому, что владелец вручную назвал ему номер.
Общая память CoWork ([16]) предупреждала об этом дословно — я не сверился.

**How to apply:** перед отправкой — только строчные. При чтении инбокса
фильтровать `to_agent__agent_id__iexact="bolt"` (FK: `to_agent__iexact` падает
с FieldError — lookup идёт по полю связанной модели, не по FK). Если письмо
«не дошло» — сначала проверить `CoworkingAgent.objects.values_list("agent_id")`
на дубликаты по регистру, а не искать баг в поллере.

Дубликат чинится переносом, не удалением почты: `filter(to_agent=stray).update(
to_agent=real)`, затем удалить пустую строку.

Связано: [[reference-cowork-message-inbox]], [[feedback-constant-communication]].
