---
name: project_live_arena_handoff
description: "Live Arena статус + хендофф трио (bolt/greenbear/ember), инфра MediaMTX не в git"
metadata: 
  node_type: memory
  type: project
  originSessionId: ba430bb2-51b5-4c12-80de-69d6249dba8d
---

2026-07-15: строим Live Arena (broadcast-арена боя) втроём. Полный хендофф — в
CoWork `CoworkingSharedMemory.load().project_memory` (запись `[LIVE ARENA HANDOFF]`).

**Готово и в проде (~v2.5.231):** превью `/chef-battle/master/live-arena/preview/`
(owner-gated) — композиция + живой snapshot + таймер + реакции + ЖИВОЕ ВИДЕО в обеих
панелях. Трекер `/chef-battle/master/live-arena/` (модель `LiveArenaStage`, 16 стадий).

**Лейны:** bolt=backend/data/инфра, greenbear=frontend арены, ember=QA/тесты/доки.

**Backend-контракты (мои):** `chef_battle/arena_snapshot.py` (`build_arena_snapshot`,
endpoint `live_arena_snapshot`); реакции `chef_battle/reaction_service.py` + `BattleReaction`
+ endpoint `arena_react`; `observer_service.py`; `clan_service.py`.

**⚠️ ИНФРА НЕ В GIT (только на сервере):** MediaMTX `/opt/mediamtx/mediamtx.yml`
(hlsVariant fmp4) + systemd `mediamtx` (RTMP:1935, HLS:8888); nginx `/hls/` блок
(`proxy_redirect / /hls/` + `proxy_cookie_flags ~ samesite=lax` — фикс cookie SameSite=None,
из-за которого видео не игралось). CSP `media-src blob` в git. hls.js самохостнут
`static/js/vendor/hls.min.js`. Ember документирует в `docs/chef_battle/live_arena_infra.md`.

**Демо (убрать по слову владельца):** тест-бой #11, авторы `livearena-test-*`, ffmpeg
`la-stream-aidan/luca` (авто-стоп 1ч). Реальный шеф: ingest `rtmp://culineire.ie:1935/<key>`,
playback `https://culineire.ie/hls/<key>/index.m3u8`.

**Ключевые баги, что я ловил (не повторять):** inline `<script>` без CSP-nonce = мёртвый
JS ([[incident_cache_ownership_500]] — тоже про прод). Осталось по лейнам см. CoWork-хендофф.
