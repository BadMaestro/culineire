---
name: Preload all tools at session start
description: Always load deferred browser and other tools immediately at the start of every session
type: feedback
originSessionId: 41497f72-e8fb-41cf-96f0-0946e152a172
---
В начале каждой сессии сразу загружать все инструменты которые могут понадобиться для работы — не ждать пока понадобится.

**Why:** Пользователь теряет время когда Claude начинает делать ToolSearch в середине задачи вместо того чтобы сразу иметь всё готовое.

**How to apply:** В начале сессии одним батчем загрузить через ToolSearch все deferred tools: Claude_in_Chrome (navigate, computer, javascript_tool, tabs_context_mcp, resize_window, read_page, find, screenshot), TodoWrite, WebSearch, WebFetch — до того как пользователь задаст первую задачу.
