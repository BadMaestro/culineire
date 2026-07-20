# Master Dependency Map

```text
arena URL -> access guard -> arena view/payload -> arena.html
  -> six Arena stylesheets
  -> _arena_render_ring.html
     -> arena_geometry.js + arena_deck.js + arena_battle_room.js + arena_render.js
     -> state/ping/popup/profile/challenge/chat/vote/gift endpoints

Arena Master Console -> same _arena_render_ring.html
Live Arena preview -> separate build_arena_snapshot contract -> privileged SVG/CSS UI
```

| Producer | Consumers | Rule |
|---|---|---|
| Models/services | views/selectors/tests | Immutable during frontend rebuild |
| `_build_arena_payload` | initial render/state poll | Preserve meanings/empty shapes |
| State/ping | deck/renderer/future 2D | Preserve timing/credentials |
| Action endpoints | popup/future controls | Preserve server authority |
| Shared renderer partial | public Arena and AMC | Decouple both before removal |
| Broadcast snapshot | Live preview | Keep distinct |
