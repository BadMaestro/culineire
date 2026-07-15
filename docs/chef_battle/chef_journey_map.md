# Chef journey map — Ember QA

Status: in progress. This is a QA navigation map, not a product specification.
Only observations marked **verified** have been reproduced locally or in the
browser. Items marked **to verify** need a signed-in browser pass with the two
test chefs.

## Test boundary

- Test chefs only: **CrestedTen** and **Jam O'Liver**.
- Never create a test battle involving GreenBear.
- Do not use Django shell to render production pages.

## Journey map

| Step | Expected transition | QA state | Evidence / next check |
| --- | --- | --- | --- |
| 1. Create challenge | Challenge form → `pending` | To verify in browser | Use CrestedTen → Jam O'Liver only. |
| 2. Opponent responds | `pending` → accepted / scheduled | To verify in browser | Response must use the correct POST action. |
| 3. Both chefs ready | scheduled → `menu_locked` | Fixed, browser verification pending | Bolt reports the former event-call 500 fixed in v2.5.233. |
| 4. Changing Room | `menu_locked` → each chef declares 5–7 unique ingredients, exactly 2 key items | Partly verified | The declaration template compiles locally after v2.5.234. Browser pass is next. |
| 5. Both menus declared | `menu_locked` → `active` | Source verified | `declare_menu()` changes status only after both declarations. |
| 6. Battle / result | active → ingredient-penalty biathlon | To verify in browser | Confirm the participant-facing CTA reaches this stage. |
| 7. Biathlon | loser places up to 2 locks; winner fires up to 3 shots | Source verified; browser pass pending | Confirm lock, hit, bounce, duplicate target and completion behaviour. |
| 8. Cooking approval | ingredient penalty → cooking | To verify in browser | Requires moderator action; then each chef uploads and confirms a real photo. |
| 9. Presentation / voting / result | cooking → presentation → voting → completed | To verify in browser | Record every CTA, access control and dead end. |

## Findings and regression checks

| ID | Finding | State |
| --- | --- | --- |
| CJ-01 | Both-ready previously failed with a 500 while creating its battle event. | Fixed by Bolt in v2.5.233; local regression test passes; needs browser regression. |
| CJ-02 | Changing Room could not render: Django rejects Python-style inline conditional syntax in a template. | Fixed by GreenBear in v2.5.234; local template compilation passes. |
| CJ-03 | The same Changing Room template had an inline script without CSP nonce. | Fixed by GreenBear in v2.5.234; browser CSP regression pending. |
| CJ-04 | Menu declaration validates 5–7 ingredients, unique names and exactly 2 key ingredients; a second declaration is rejected. | Source verified; test validation messages in browser. |
| CJ-05 | Biathlon service limits total locks and shots, but does not reject repeated shot targets. | Source finding; confirm intended rule before filing as defect. |
| CJ-06 | Cooking can start only through the moderator approval service from ingredient-penalty state. | Source verified; verify UX and moderation handoff in browser. |

Local regression run on 2026-07-15: `BattleSetReadyTests` and
`DeclareMenuServiceTests` — 12 tests passed.

## Current next actions

1. Re-run CrestedTen/Jam through Changing Room on v2.5.234 when a signed-in
   browser tab is available.
2. Continue from the first reachable post-biathlon state and add browser evidence.
3. Send confirmed blockers to Bolt/GreenBear via CoWork; keep this map current.
