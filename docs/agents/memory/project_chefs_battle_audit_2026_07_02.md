---
name: chefs-battle-audit-2026-07-02
description: "Полный аудит Chef Battles 2026-07-02 — Arena-промпт выполнен целиком, флаг CHEF_BATTLE_ENABLED на проде ВЫКЛЮЧЕН, 0 завершённых битв, список недоделанного"
metadata: 
  node_type: memory
  type: project
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

Аудит 2026-07-02 (по Final Arena Prompt.yaml + roadmap + deployment journal):

**Arena-промпт (7 шагов) выполнен полностью** — Phase FE-2 роадмапа, задеплоен 2026-07-01, проверено в коде и вживую на проде (корона в центре арены рендерится, latest_result в JSON есть).

**Состояние прода (проверено публичными запросами 2026-07-02, прямой доступ к БД запрещён классификатором разрешений):**
- CHEF_BATTLE_ENABLED = False на проде: страницы под @chef_battle_guard (home, rankings, season, tokens, hall-of-fame) отдают анониму 404; без guard'а (arena, rules, artifacts) — 200. Dark launch: видят только staff/bearseeker.
- Завершённых битв: 0 (latest_result: null) → Phase 3 "First 5-10 sandbox battles" = 0/5.
- Держатель короны есть; шефов на арене ~4 (GreenBear, CrestedTen, Oscar Korkins, Jam O'Liver).

**Не доделано (скорректировано владельцем 2026-07-02):**
- ИСКЛЮЧЕНЫ из роадмапа решением владельца: outreach-лист 30-50 фуд-криэйторов и AllFresh sponsor pilot. Код роадмапа (_build_battlefield_progress в chef_battle/views.py, Phase 3) на 2026-07-02 ещё показывает их как pending — надо убрать при обновлении роадмапа.
- ПЕРЕНЕСЕНЫ В ДО-ЗАПУСКА (владелец, 2026-07-02): clan/team battles (ВЫСШИЙ приоритет из трёх), sponsor battle integration (больше НЕ привязан к AllFresh-пилоту), TikTok/Instagram live-интеграция. В коде роадмапа они всё ещё в Phase 6 "после запуска".
- Остальное до запуска: первые 5-10 sandbox-битв (0/5), ручная модерация первых 20-30 битв, затем включение флага CHEF_BATTLE_ENABLED.

**Хвосты внутри "done":** Stripe Connect реальный API (live keys, ENABLE_STRIPE_CONNECT_PAYOUTS=False), live video провайдер Mux/Agora/LiveKit (ENABLE_LIVE_VIDEO=False), frontend Live Battle Agreement, live report button + auto-pause, ENABLE_AI_IMAGE_REVIEW_PROVIDER=False.

**Найденные гэпы:** (1) легаси-зелёный → ИСПРАВЛЕНО 2026-07-02 с одобрения владельца: все #1a6b3a/#d6f5e0/#6dce8f/#bfedd0/#4db877 заменены на золотую семью (#c8942a акцент, #f8d28a фон пилюль, #6e4e2c тёмный текст) в 9 файлах; паттерн var(--color-success, ...) удалён (переменная нигде не определялась); (2) generate_battle_assets.py + combat_items.md → ИСПРАВЛЕНО 2026-07-02: 7 фэнтези-записей переименованы в ирландский паттерн (Salamander Grill Sauce, The Dagda's Ladle, Skellig Stone Stockpot, The Ogham Cutting Board, The Tír na nÓg Wok, Giant's Causeway Dome, Nuada's Silver Pot Lid; руны → огам); (3) blast-ring ещё ни разу не сработал от реального события (0 завершённых битв).

**Демо-виджет для GreenBear жив:** /chef-battle/arena/?demo — панель "Duel stages · demo" (5 стадий: Empty, Crown, VS centre, Ripple, Blast; поллинг заморожен); /chef-battle/arena/?demo=vs — серверный стейджинг VS-центра двумя реальными шефами (только залогиненным).

**Хореография дуэли (видение владельца vs код, проверено 2026-07-02):** реализовано — курсор нож+мусат только на шефах в активной битве, VS-центр (2 восьмигранные ячейки + VS) на время битвы с автовозвратом к короне/пустоте, blast для всех посетителей арены, полный пайплайн завершения (рейтинг ±25/-15, корона 24ч, уведомления, дропы, статы). НЕ реализовано: (а) переезд аватаров в соседние ячейки друг напротив друга после принятия вызова (prep-фаза); (б) перенос в центр как переезд — сейчас аватары дублируются (центр + своя ячейка); (в) назначенное время баттла + гейт готовности обоих — битва стартует сразу после accept; (г) зрительский попап на арене (смотреть/чатиться/голосовать не уходя с арены) — флоу живёт на battle_detail; (д) sitewide blast — на страницах вне арены завершение битвы не даёт blast (нет глобального поллинга latest_result); (е) озвучка имени победителя (аудио).

**Внешнее (docs/external_setup_checklist.md — OPEN):** Pinterest Business/Rich Pins, Telegram BotFather, Buffer/Instagram/TikTok. month1_decisions.md: Image Optimisation, Ads, Affiliate Links отложены до трафика.
