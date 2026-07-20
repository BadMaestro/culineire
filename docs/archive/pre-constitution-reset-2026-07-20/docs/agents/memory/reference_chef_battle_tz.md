---
name: reference-chef-battle-tz
description: "Где хранится ТЗ Chef's Battle — все спецификации закоммичены в репозиторий"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 54e34f70-f718-4f1f-a375-9e6d18758d42
---

Все ТЗ-документы Chef's Battle находятся в репозитории по пути `docs/chef_battle/`:

| Файл | Содержимое |
|---|---|
| `tz_main.md` | Полное ТЗ — все 30 разделов, механика, фазы, UI-требования |
| `artifact_1_developer_prompt.md` | AI developer prompt для Claude/Codex |
| `artifact_2_backlog.md` | Бэклог Phase 0 + Phase 1, тикеты CB-0001 — CB-1603 |
| `artifact_3_models_rules.md` | Модели, статусы, бизнес-правила, phase map |
| `claude_master_prompt.md` | Мастер-промпт: роль Senior Web Developer / Game Architect |
| `project_discipline_addendum.md` | Definition of Ready/Done, фазовая дисциплина, event-first правила |
| `operational_constraints.md` | Правила веток, коммитов, деплоя, production safety |
| `response_format.md` | Формат ответов, YAML-отчёты, структура handoff |
| `developer_role.md` | Описание роли разработчика и продуктовых слоёв |
| `executive_summary.md` | Краткое резюме проекта |

**Как использовать:** в начале каждой сессии по Chef's Battle читать нужные файлы через Read tool. Не просить пользователя загружать документы повторно.
