# Chef Battle — independent audit, GreenBear, 2026-08-10

**Production at audit time:** v2.5.986 / `b6c19412`, equal to `origin/main`.
**Mode:** READ-ONLY. No code changed, nothing deployed, no privilege flag
written, nothing touching `greenbear` (AGENTS.md §18, §20).
**Reference corpus:** `docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md` v1.1.0 **and**
the eighteen game-rule documents under `docs/chef_battle/` restored to ACTIVE on
2026-08-05, plus `tz_main.md`.

## 0. Why this audit is not a repeat of Bolt's

Bolt's act of 2026-08-10 measured the code against the **product contract** — 58
substantive points, 71% implemented. That contract governs presentation and
access. It is not the rules of the game.

The rules of the game are the eighteen documents §10 restored as BINDING on
2026-08-05, and they have **never been reconciled against the code**. The
2026-08-05 pass was a sweep, not a reconciliation. So this audit has two halves:
every one of Bolt's findings re-checked with my own evidence, and the layer
nobody has measured.

Every number below carries the command that produced it and its blind spot.

---

## 1. Bolt's findings, re-checked

> **F1–F5 were fixed while this audit was being written** — `fc0d8bcc`,
> shipped as **v2.5.988**, live. I verified the fix rather than take the commit
> message for it: `token_checkout_create` and both gift views now carry
> `@chef_battle_guard`; `author_detail` calls `is_battle_visible()` directly;
> `handle_no_show_battles` takes `_locked_battle()` and re-verifies status and
> deadline under the lock; `issue_reward` uses a DB-side atomic increment.
> **The table below records what I found when I looked, which is the state
> those fixes were made against.** One residue survives them — see 1a.

### 1a. What the fix left behind: the three endpoints are still discoverable

`chef_battle_guard` was added as the **innermost** decorator on all three, under
`@require_POST` and `@login_required`. Those answer first, so to an anonymous
prober on production **after** v2.5.988:

```
GET /chef-battle/arena/                       404   ← invisible, correct
GET /chef-battle/tokens/checkout/             405   ← "wrong method", so it exists
GET /chef-battle/battles/1/gift/appreciation/ 302 → /accounts/login/?next=…
```

The security hole is genuinely closed: an authenticated non-staff caller now
reaches the guard and gets a 404. What remains is that these three URLs still
announce their own existence during a dark launch, where every other gated
surface answers 404. Moving `@chef_battle_guard` to the top of each stack costs
one line each and makes them behave like the rest of the arena.

| # | His claim | My verdict | My evidence |
|---|---|---|---|
| F1 | `recipes/views.py:1457-1465` re-implements the gate and keeps `has_bearseeker_privileges` | **CONFIRMED** | Read the lines. `is_battle_visible()` is `flag or is_staff or is_superuser`; this copy adds `_ap.has_bearseeker_privileges`. Strictly wider. |
| F2 | `token_checkout_create` creates a real Stripe session with no visibility gate | **CONFIRMED, and worse than stated** | Decorators are `@require_POST @login_required` only; the four fraud gates check suspension, fraud flag, age and consent — none checks visibility. **Measured on production:** `GET /chef-battle/token-shop/` → **404**, `GET /chef-battle/tokens/checkout/` → **405**. A 404 means invisible; a 405 means the view was reached and only objected to the method. |
| F3 | Both gift endpoints ungated | **CONFIRMED on production** | `GET /chef-battle/battles/1/gift/appreciation/` and `…/gift/artifact/` → **302 to `/accounts/login/?next=…`**, while `/chef-battle/arena/` → 404. The gated surface hides; these two invite a login. |
| F4 | `handle_no_show_battles` can award a win twice | **CONFIRMED; premise verified on the server** | No `select_for_update` at `services.py:501-507`, while `calculate_battle_result` (`:829-843`) and `resolve_start_rituals` both take `_locked_battle()`. The cron premise is real: `crontab -l` on the box shows `*/15 * * * * … expire_stale_battles`, and the command carries no `flock` and no mutex. **Blind spot:** the job currently processes 0 rows (`expire_battles.log`), so the overlap is latent, not observed. |
| F5 | `issue_reward` loses tokens under a race | **CONFIRMED** | `:2167-2170` is a read-modify-write on the wallet while only the `RewardRecord` is locked. Two records for one recipient lock different rows. Every other money path in the same file is safe: `credit_tokens` uses `F()`, `debit_tokens` a conditional atomic `UPDATE`, `reverse_reward` `select_for_update()` on the wallet at `:2229`. |
| F6 | Enrolment and age confirmation ungated | **CONFIRMED; one detail wrong** | `GET /chef-battle/enroll/` and `/age-verification/` → 302 to login on production. His text says enrolment grants "tokens"; `award_enrol_bonus` grants **battle moves**, not tokens. The gate finding stands; the currency named does not. |
| F7 | Parts of the battle flow gated inconsistently | **CONFIRMED** | `battle_changing_room`, `battle_recipe_attach`, `biathlon` are exempt in `UNGUARDED_BY_DESIGN` while their neighbours `battle_declare_menu`, `biathlon_lock`, `cooking_submit` carry the guard. |
| F8 | `is_moderator` still keys on `has_bearseeker_privileges` | **CONFIRMED, and currently harmless** | `accounts/views.py:30-41`. Grant sets `is_staff=True` (`:351`) **and revoke clears it** (`:365`), so the two flags now move together in both directions. The invariant holds by two call sites agreeing, not by the data or by `is_moderator()` itself. |
| F9 | Rank is not re-checked when a challenge is accepted | **CONFIRMED** | `check_rank_matchup` is called from exactly one place: `views.py:1750`, `challenge_create`. `accept_challenge` re-validates the *recipe's* status inside the 12-hour window and says so in its own comment (`services.py:355-359`) — the same window, the same reasoning, and the rank is not re-read. |
| F10 | The template reveals on phase name, not on `is_revealed` | **CONFIRMED** | `battle_detail.html:341` ORs the flag with three status names; `reveal_entries_if_ready()` is the only writer and `operator_force_status` does not call it. |
| F11 | Personal pages without an explicit arena gate | **CONFIRMED, low** | As described; each checks "this is my account". |
| T1 | `TokenWallet` instead of the contract's `TokenAccount`, and "wallet" in the legal VAT text | **CONFIRMED** | `models.py:1062`; `templates/legal/purchases_and_vat.html` lines 123, 144, 146, 148. |
| T2 | Raw hex instead of Arena tokens | **CONFIRMED, count corrected** | Not a handful of lines: **71** raw hex literals in `arena.css` and **14** in `arena_atmosphere.css`. |
| Dead code | 4 artifacts | **3 confirmed, 1 refuted** | `guide.html` (its view always redirects) and `_battle_wordmark.html` (zero includes) are unreferenced; `CosmeticItem`/`ChefCosmetic` are admin-only. **`arena_octant_prototype.js` is NOT dead code:** its second line reads "Isolated Arena geometry prototype — intentionally not loaded by production", and AN18 already classified it as deliberate in the release journal. Listing it as dead contradicts his own earlier audit and §15. |
| CSS | `chef_battle.css` loaded twice on 39 templates | **CONFIRMED — 40 templates** | `base.html:76` loads it at `?v=20260618-hero-menu` whenever the flag is on; **40** further templates load it again in `extra_head` under a different `?v=`. Two distinct URLs for one 138 630-byte file, so the browser downloads and parses it twice, and the two caches can hold different generations of it. |
| CSS | ~120 dead rules, ~14 shared selectors | **NOT REPRODUCED at his figures** | My own parse: **46** selectors appear in both remaining sheets; 57 selector+property pairs are written more than once with an identical value. **Blind spot, stated plainly:** my parser flattens `@media`, so some of those are legitimate responsive overrides, and I did not verify the ~120 dead rules against a rendered DOM. His figure may be right; I could not confirm it, and neither could he with the tools in this repository — see 3.7. |

**Score on his act: 13 of 15 lines stand, one materially corrected, one refuted.**
Where I disagree, I disagree with the classification, never with his reading of
the code.

---

## 2. What his audit did not cover: the game rules against the code

This is the half nobody had measured. Verdicts: **HOLDS / MISSING /
CONTRADICTS**.

### 2.1 Settled by the Owner, and the code is right — no action

| Document | Requirement | Verdict |
|---|---|---|
| `moves_economy.md` | earn 5/5/10/1/1/1 | HOLDS — `energy_service.py:22-27` |
| `moves_economy.md` | combat investment 1–5 | HOLDS — `services.py:1208-1209` |
| `moves_economy.md` | 10 moves minimum to challenge | HOLDS — `MOVES_MIN_TO_CHALLENGE = 10`, enforced at `views.py:1737` |
| `token_economy.md` | eight packages, doubling, 0→40% discount | HOLDS — `token_config.py`, exact match |
| `battle_rules.md` | 12-hour acceptance window | HOLDS — `forms.py` |
| `battle_rules.md` | 48h submission + 2 days voting | HOLDS — `accept_challenge():329-330` |
| `battle_rules.md` | second place is paid half, draw pays both | HOLDS — 12/7/5 and 6 moves, exactly half of 25/15/10 and 11 |
| `battle_rules.md` | withdrawal: 3 per account, ceiling 15/3, moderator final | HOLDS — `withdrawal_service.py` |
| `ingredient_combat.md` | equal ingredient counts, exactly 2 keys, 2 locks | HOLDS — `MIN_COUNT 5 / MAX_COUNT 7 / KEY_COUNT 2 / MAX_LOCKS 2` |

### 2.2 Rules that are NOT implemented

| G# | Document | Rule | State of the code |
|---|---|---|---|
| **G1** | `battle_rules.md` §"Slot system" | **"One battle slot per chef. A chef with an active battle cannot accept or issue new challenges."** | **Not enforced anywhere.** No `has_active_battle` check in `challenge_create`, in `BattleChallengeForm`, or in `accept_challenge`. The nearest gate is `gate_post_battle_cooldown` (24h *after* finishing), which is a different rule. Nineteen fraud gates exist; none of them is this one. **Blind spot:** production currently has 0 active battles, so nothing has manifested. |
| ~~**G2**~~ | `chef_levels.md` | ~~A CulinEire Hero may fight only other Heroes~~ | **WITHDRAWN — my error, corrected by the Owner 2026-08-10: «у нас нет понятия Герой».** There is no Hero tier and there never shipped one; X09 buried it on 2026-08-05 and the board says so in as many words. `is_hero` is **his own flag** — set only in `get_or_create_battle_profile()` for `OWNER_SLUG`, true on exactly one production account, `greenbear`. So the branch in `check_rank_matchup()` is not "heroes fight anyone", it is the Owner standing outside the rank window, which is §18 and not progression. I read an unreconciled document literally and reported a tier the product does not have. What genuinely remains is cosmetic: three templates still print the words "CulinEire Hero" for that flag. |
| **G3** | `chef_levels.md` | Artifact tier from cooking format — webcam wins draw Rare/Epic/Legendary, photo wins draw Common/Uncommon | **Missing entirely.** `cooking_format` does not exist in the Python source. `_DROP_WEIGHTS_WINNER` (`services.py:2082`) is one table for every battle. |
| **G4** | `hall_of_fame.md` | "The Founding Ten" (`is_historic` on the first 10 battles) and the "Board of Memory" (first 20 chefs) | **Missing entirely** — no field, no model, no page. Time-sensitive by nature, though reconstructible from ordering afterwards. |
| **G5** | `battle_lifecycle.md` §"Ready" | Three steps: A ready → B ready **and proposes a time** → A confirms | Half-built. `proposed_combat_time` and `combat_time_confirmed` exist on the model and **nothing ever writes them** (one read in `selectors.py:347`). What runs is the Owner's later A6 rule — both ready pulls the start to 15 minutes — which supersedes; the two dead fields are the residue. |

### 2.3 Rules where the document and the code disagree — **yours to rule on**

Per §10 the code is not automatically wrong here. Four of these are money.

| X# | Subject | Document | Code |
|---|---|---|---|
| **X12** | Appreciation gift prices | `audience_gifts.md`: flowers 5, coffee 5, beer 10, cocktail 15, whiskey 20 | `models.py:725`: coffee 20, beer 30, whiskey 50, flowers 80, cocktail 80, **champagne 100** — a sixth item the document does not have. Every price differs; the cheapest is 4× the documented one. |
| **X13** | What a battle artifact actually costs | `token_economy.md` / `audience_gifts.md`: 10 / 25 / 60 / 150 / 400 by rarity | `send_battle_artifact()` charges **double** — the artifact plus a delivery fee equal to it (`services.py:1965-1967`). A Common artifact documented at 10 tokens costs 20. |
| **X14** | Who enforces the artifact price | The rarity table is the rule | `Artifact.RARITY_TOKEN_COST` (`models.py:600`) is **referenced by nothing**. The charge is the per-row `token_cost`, default **10**. Production data is correct today (measured: common 10, uncommon 25, rare 60, epic 150, legendary 0–400) but nothing holds it there: a new Epic added through the admin costs 10 tokens until someone remembers. |
| **X15** | Winner's move reward | `battle_lifecycle.md` Phase 9: "+5 moves" | `moves_economy.md` and the code: **+10**. Two active documents contradict each other; the code follows the one you already settled (X07). |
| **X16** | Clans versus Factions | `cuisines_design.md` header: **"Supersedes `clans_design.md` — the clan/kitchen idea is dropped"** | Both are built, both are routed (`urls.py:38-47`), and `clans_design.md` is still on the §10 ACTIVE list. Production: **28 factions, 0 members; 0 clans, 0 memberships**. Two competing systems for one idea is what §7 forbids. |
| **X17** | Battle statuses | `battle_lifecycle.md` names 10, including `declared` and `accepted` | The code has **16**, and those two are not among them — they live on `BattleChallenge` instead. The document's phase spine is right; its status list is stale. |

---

## 3. My own findings, outside both his list and the documents

### 3.1 — HIGH, visible — the menu declaration speaks Russian to the user

The whole Changing Room path answers in Russian on an English-language Irish
site. `chef_battle/services.py:1580-1605` — six user-facing `ValueError`
messages, all displayed verbatim by the view. `views.py:3262` —
`messages.success(request, "Меню объявлено. Ждём соперника!")`.

Worst of them, `services.py:1629`:

```python
create_battle_event(..., message="Оба шефа объявили меню. Бой начинается!",
                    is_public=True)
```

`is_public=True` puts that sentence in the public battle event feed, which the
arena and the sitewide news read. **Blind spot, measured:** production carries
**0** such events today, because no battle has reached that stage — it is
loaded, not fired. This is the only Cyrillic in user-facing code on the whole
site; everywhere else it appears only in comments quoting you.

### 3.2 — MEDIUM — the moves path is the one subtraction that skips the §18 gate

§18 names the marker explicitly: `OWNER_SLUG`, **never** `infinite_moves`,
"that flag is on three production accounts and does not mean the Owner". Every
subtraction of rating, reputation, losses and streak does go through
`penalise()`/`is_immortal()` — I swept for it and found no other writer:

```
grep -rn "\.rating -|\.rating =|\.reputation|\.losses +|\.win_streak = 0" chef_battle/
→ only services.py:182-198 (inside penalise) and services.py:91 (owner bootstrap, raising)
```

But `energy_service.spend_moves():246` guards on `profile.infinite_moves` — the
exact flag §18 forbids using as the marker. Measured on production: **five**
accounts now carry `infinite_moves`, not three (`greenbear`, `crestedten`,
`jam-oliver`, `emu-chef-alpha`, `emu-chef-beta`). Your account carries it, so
you are protected today — by a flag that means something else and is spreading.

### 3.3 — LOW — your live profile never received the owner bootstrap

`get_or_create_battle_profile()` sets rank, 3 stars, hero, rating 9999 and 15
wins **only when the row is created**. Yours predates that code: production
reads `rating 0, wins 0, rank culinary_master`. Nothing is broken — `promote_rank`
only ever raises and `is_immortal` returns before any penalty — and I have not
touched it and will not (§18). Reported because a 0 rating on the crown holder
is a thing you may see on a screen and wonder about.

### 3.4 — LOW — a double accept answers with a 500, not a second battle

`challenge_respond` checks `status != PENDING` outside any lock and
`accept_challenge` takes no row lock. Two simultaneous accepts both pass the
check; the `OneToOneField` on `Battle.challenge` (`models.py:205`) then refuses
the second at the database, so the data stays correct and the second user gets
an `IntegrityError`. A real edge, a cheap fix, no corruption.

### 3.5 — What is genuinely solid, said out loud

Vote integrity is complete: `gate_self_vote`, `gate_participant_vote`,
`gate_duplicate_device`, `gate_vote_rate_ip`, suspension and fraud, all wired in
`battle_vote` (`views.py:2103-2109`), with a database constraint behind them.
Result calculation is idempotent and locked (`services.py:829-843`). The dark
launch holds anonymously on production: `/chef-battle/arena/`,
`/chef-battle/master/`, `/chef-battle/token-shop/` and the broadcast page all
answer **404**; only `/chef-battle/rules/` answers 200, which is the one
exception you named yourself.

### 3.6 — The guard census, counted independently

84 routed `chef_battle` views. **53** carry a guard decorator, **25** are
listed in `UNGUARDED_BY_DESIGN` with a stated reason, 1 is an admin route gated
by `admin_view` plus a model permission and covered by its own test, and the
remaining 5 are name-mismatch artefacts of my keying by URL name where the code
keys by function name. The mechanism is sound. **The judgement inside it is
where F2, F3 and F6 live: three of those 25 exemptions let an unreleased feature
take real money.**

### 3.7 — MEDIUM, live on production — two artifacts are spelled `defense`, everything else says `defence`

`Artifact.effect_type` is a free-text `CharField` with no `choices`. Production
carries both spellings, measured:

```
attack 105 · defence 100 · defense 2 · boost 4 · unlock 1 · blank 1   (213 rows)
```

Three consumers, three different behaviours:

- `services.py:1270` normalises `defence`→`defense` before comparing, so **combat
  itself is correct**;
- `views.py:3005` lists both spellings, so the chest filter is correct;
- **`views.py:1238` matches `"defence"` exactly**, so the defence power shown on
  the arena silently omits those two artifacts — `The Butter Shield` (epic,
  effect value **9**) and `Rusty Pan of Survival` (common, 1).

**CORRECTED BY THE OWNER TWICE, and the second time mattered.** I first wrote
"four chefs today". It is four `ChefArtifact` rows across **two** accounts,
`crestedten` and `jam-oliver`. I then called those test chefs, and he corrected
that too: **they are real accounts, his own, which he uses for testing.** So
neither of my wordings was right. The accurate one: two of the Owner's own
accounts carried the artifacts and would have been shown a defence total lower
than they own; no third-party chef held either, and no live battle existed, so
the impact was latent while the defect was not. The code path is wrong and would undercount the moment a real
chef held one; that is the finding, and it is the whole of it. The absence of
`choices` on the field is what allowed it.

### 3.8 — `combat_items.md`, reconciled

| Requirement | Verdict |
|---|---|
| 100 attack + 100 defence | Production has 105 attack, 102 defence, 213 total |
| `max_bonus` always 3 | Contradicts `COMBAT_MOVES_MAX = 5`, which you settled as correct in X08 — the document is the stale side |
| `item_type`, `base_power`, `combat_log_text`, `emoji` fields | Not on `Artifact`; the model carries `effect_type` / `effect_value` instead. A rename, not a gap — but 3.7 is the cost of the field it was renamed into. |

### 3.9 — The audit tooling in this repository does not run

`ops/audits/arena/tools/README.md` says these instruments were committed
precisely so they would stop being lost with every session. Two of them —
`css_cross1.py` and `css_order_risk.py`, the two that measure duplicate CSS —
import `tools/scratchpad/css_supersede.py`, **which is not in the repository**.
Both die on import. The tool written to stop the loss was itself committed
incomplete, which is why neither he nor I can reproduce the ~120-dead-rule
figure with the project's own instrument.

---

## 4. The numbers, and what each one counts

I refuse to publish one global percentage: it would need a denominator nobody
has enumerated, and an invented denominator is exactly the number §17.15.5
forbids.

| Slice | Result | Denominator |
|---|---|---|
| Product contract (Bolt's) | **71%**, unchallenged | 58 substantive points he enumerated; I did not re-count them, I re-checked his findings |
| **Game rules, the documents I reconciled** | **9 HOLD, 5 MISSING, 8 CONTRADICT** | 22 checkable requirements across 10 documents |
| **Documents still unreconciled** | **8 of 18, plus all 1269 lines of `tz_main.md`** | `artifact_3_models_rules`, `battle_chat`, `clans_alliances_rules`, `chef_journey_map`, `arena_data_layer_spec`, `arena_mockup_spec`, `ARENA_HALL_PLAN`, `clans_design` |
| Access gates | 53 guarded + 25 deliberate + 1 admin, of 84 | the routed view list, enumerated by resolver walk |
| §18 | **holds for every penalty; one gap in the moves path** | 5 writable fields swept |

**The honest headline is not a percentage.** It is that the game's own rulebook
has been binding for five days and slightly under half of it has now been read
against the code for the first time — and that first half already yields five
rules that were never built and six places where the document and the code
charge different money.

---

## 5. What I recommend, in order

**Done since this act was written.** F1–F5 (v2.5.988, Bolt). **3.1, 3.7 and 1a**
— the Russian strings, the `defense` spelling and the three announcing URLs —
shipped as **v2.5.989** on his order, with three guard tests. **X12, X13, X15,
X17, X18** — settled by him and the documents corrected in **v2.5.991**.
**G2 withdrawn** as my error.

### The Owner's standing rule that settles most of the rest

**2026-08-10, verbatim:** «ТЗ писалось долго и несколько раз переписывалось —
код уточнялся по факту и уточняющие вопросы задавались по факту — поэтому я
склонен больше доверять коду — ТЗ и правки нужно адаптировать.»

So where a document and the code disagree about a **decision**, the code is the
decision and the document is adapted. This does **not** cover a rule the code
never implemented: **absence is not a decision.** That line is what separates
the two lists below, and it is the reason G1, G3 and G4 stay open while X12–X18
closed the same day.

### What is left

1. **G1, the one-slot rule** — and read it in full, because it is wider than I
   first reported: the slot is occupied **the moment a challenge is issued**,
   and an occupied slot forbids **accepting** as well as issuing. Nothing in the
   code models a slot at all. The nearest three gates are 3 challenges a day,
   24 hours on a repeat pair, and 24 hours after a COMPLETED battle — none of
   them this. Build it or drop it; absence is not a decision.
2. **X14** — `RARITY_TOKEN_COST` is referenced by nothing, so a new artifact
   costs whatever the admin form defaults to (10) regardless of rarity. The data
   is correct today and held there by nobody.
3. **G3 and G4** — artifact tier by cooking format (the field does not exist),
   the Founding Ten and the Board of Memory. **Owner, 2026-08-10: «этого ещё и
   вправду нет — будем строить».** Confirmed missing and confirmed wanted; they
   are scheduled work waiting on a card from him, not open questions any more.
4. **X16** — clans and factions both built and both routed, while
   `cuisines_design.md` says in its own header that factions supersede clans.
   28 factions and 0 clans on production.
5. **The eight documents nobody has read against the code yet**, plus all 1269
   lines of `tz_main.md`. This act covered ten of eighteen.

Everything in section 3 that is not listed here is shipped or withdrawn.

---

## 6. The test baseline this audit stands on

```
manage.py test chef_battle config recipes --noinput --parallel 8
Ran 1036 tests in 803.820s — OK (skipped=2)
```

PostgreSQL, eight workers on the eight logical threads of the i7-2600,
`CHEF_BATTLE_ENABLED` in its **default** state. Recorded so the findings below
cannot be confused with a broken tree: **every one of them is green code doing
exactly what it was written to do.** That is the point. Not one of the
twenty-odd defects in this act is caught by 1036 passing tests — the suite tests
the code against itself, and this audit tests it against the rules.

The three that a test would have caught cheaply, if anyone had written it:
the one-slot rule (G1), the artifact price table nothing enforces (X14), and the
`effect_type` spelling (3.7).

---

## 7. Every challenge he made to this act, and what it changed

He read the act and pushed back six times in one evening. Collected here because
the answers were scattered across five files and a chat, which is how a
correction gets lost. Two of the six were my errors, and both are marked as
such.

| # | His words | What it changed |
|---|---|---|
| 1 | «подарки стоят в 4+ раза дороже написанного — **где**?» | Fair: my summary was loose. It is the six **appreciation** gifts, not combat artifacts, and the spread is **2.5× to 16×** — coffee ×4, flowers ×16, cocktail ×5.3, beer ×3, whiskey ×2.5 — plus a sixth gift the document never had. Combat artifact prices matched exactly all along. |
| 2 | «доставка подарка стоит в два раза дороже — и это **правильно**… это плата за право сделать подарок в активном бою» | **His ruling, X13.** Not a defect: the doubling is the price of intervening in a running fight. The documents were silent about the fee, which is what made them look like they disagreed. Both now state fee and total beside the price. No code changed. |
| 3 | «audience_gifts.md — в коде правильные цены» | **His ruling, X12.** Document corrected to the code, generated from its own labels, emoji and `APPRECIATION_GIFT_COST`, and pinned by a test that reads it in both directions. |
| 4 | «что именно говорит правило — один бой на шефа? ты меня дезинформируешь — ты обязан читать правило **полностью**» | **He was right and the gap is WIDER than I reported.** I quoted only the first clause. In full: the slot is occupied **the moment a challenge is issued**, and an occupied slot forbids **accepting** as well as issuing; it frees when the challenge expires unanswered or the battle completes. Nothing in the code models a slot at all — the three nearest gates are 3 challenges a day, 24h on a repeat pair, and 24h after a COMPLETED battle. G1 stands, restated. |
| 5 | «у нас нет понятия — Герой, откуда ты его взял?» | **My error. G2 WITHDRAWN.** From `chef_levels.md`, which describes a tier X09 buried on 2026-08-05 — the board says so in as many words. `is_hero` is **his own flag**: set only in `get_or_create_battle_profile()` for `OWNER_SLUG`, true on exactly one production account. The `check_rank_matchup()` branch is §18, not progression. I read an unreconciled document literally and reported a tier the product does not have. |
| 6 | «сейчас на арене нет ни одного реального боя — и ни одного реального шефа» | **My error, corrected in four places.** I wrote "four chefs today". It is four `ChefArtifact` rows on **two** accounts. **Latent, not manifest.** |
| 7 | «crestedten и jam-oliver — это реальные аккаунты, но мои, я их использую для тестов» | **My second wording was wrong too.** I had relabelled them "test chefs", which reads as fixtures. They are **real accounts that belong to him**, used for testing — so the accurate statement is that two of his own accounts would have been shown a defence total lower than they own, no third-party chef held either artifact, and no live battle existed. Corrected in the journal, the view comment, the test docstring and section 3.7. Worth stating once as a rule for whoever audits next: **an account being used for testing is not test data**, and nothing about it is safe to treat as disposable. |

And one more, which is not a challenge but the rule that settles most of what is
left:

> «ТЗ писалось долго и несколько раз переписывалось — код уточнялся по факту и
> уточняющие вопросы задавались по факту — поэтому я склонен больше доверять
> коду — ТЗ и правки нужно адаптировать.»

**Its boundary, which he did not have to state and which every correction here
respects: it settles a DISAGREEMENT, where the code is the decision. It does not
cover a rule the code never implemented — absence is not a decision.** That is
why X12–X18 closed the same day and G1, G3 and G4 did not.

### The scoreboard on my own act

Of everything I put in front of him: **two findings were wrong** (G2 withdrawn
entirely, 3.7 overstated from latent to manifest), **one was understated** (G1,
wider than reported), **five were settled by his ruling in the code's favour**
(X12, X13, X15, X17, X18), **three were confirmed as real and wanted** (the
Founding Ten, the Board of Memory, artifact tier by format — «будем строить»),
and the rest stand as written. Recorded because an audit that never reports its
own error rate is asking to be trusted rather than checked.

---

## 8. The other half: the eight remaining documents and `tz_main.md`

Ordered by his instruction of 2026-08-11. Same method and the same boundary:
where a document and the code disagree about a **decision**, the code is the
decision (his standing rule); where the code never implemented the rule at all,
that is **absence, not a decision**, and it is his to settle.

**Three of my own earlier findings are corrected here.** Reading the second half
made the first half more accurate, which is the argument for finishing an audit
rather than shipping it in pieces.

### 8.1 What holds

| Requirement | Source | Evidence |
|---|---|---|
| The eight-rung rank ladder, in order | `tz_main.md` §10 | `ChefBattleProfile.Rank` — Kitchen Porter → Culinary Master, exact match |
| Crown lasts 24 hours, time-based, granted on a win | `tz_main.md` §11, `artifact_3` §10 | `services.py:953`, `crown_until`, `has_crown` reads `> now` |
| Only APPROVED content grants moves | `tz_main.md` §16 | `recipes/signals.py:111` and `articles/signals.py` gate on `status == APPROVED` **and** on it not already having been approved, so a re-save cannot farm moves |
| Cooldown between the same pair; daily challenge limit; vote anomaly logging; rate limits; IP/device/session checks | `tz_main.md` §16 | `gate_repeat_challenge_cooldown`, `gate_challenge_spam`, `VoteIntegrityEvent`, `ratelimit`, `gate_duplicate_device` / `gate_vote_rate_ip` |
| The strongest artifacts are never sold | `tz_main.md` §15 | Legendary is prize-only; `send_battle_artifact` refuses it by name |
| Clans are built on the Faction taxonomy, with alliances and the observer seat | `clans_alliances_rules.md` | `Clan.categories` M2M → `Faction`, `SeasonArenaObserver`, `observer_service.py` |
| The battle lifecycle a QA map describes | `chef_journey_map.md` | Steps 1–9 all exist as routes and services; it is a QA map, not a spec, and it says so in its own first line |

### 8.2 Corrections to my own earlier findings

**G4 was wrong — the Hall of Fame is half-built, not absent.**
`/chef-battle/hall-of-fame/` exists and renders two lists:

- **The Founding Ten IS implemented**, by ordering rather than by a flag:
  `get_hall_of_fame_battles()` takes the first ten completed battles.
- **The Board of Memory is NOT.** `get_hall_of_fame_chefs()` returns the top
  twenty **by wins**, which is a leaderboard. `hall_of_fame.md` asks for the
  first twenty chefs ever to **participate** — a pioneer list, permanent, and
  not a ranking. Those are different sets, and only one of them can be second.

**And the founding ten are not permanent, which is a defect in itself.** The
selector orders by `updated_at`, and `Battle.updated_at` is `auto_now=True`
(`models.py:235`). Any later write to a completed battle row — a moderation
note, a dispute, a withdrawal resolution, an operator touch — moves it to the
end of that ordering and **silently evicts it from the founding ten**, letting a
newer battle take its place. `hall_of_fame.md` uses the word "permanently".
Ordering by `created_at`, or by the `is_historic` flag the document asks for,
fixes it; ordering by a column that changes cannot.

**X16 was wrong — clans and factions are not two competing systems.** I read
`cuisines_design.md`'s header ("supersedes `clans_design.md` — the clan idea is
dropped") and stopped there. `clans_alliances_rules.md` is the LATER document
and it revives clans in a new shape, layered **on top of** factions: a clan
picks up to three **Faction** rows as its categories, and the code implements
exactly that (`Clan.categories` is an M2M to `Faction`). The stale line is the
supersede note in `cuisines_design.md`, not the code.

### 8.3 Absence — not built, and his to settle

| ID | Requirement | Source | State |
|---|---|---|---|
| **G6** | **Culinary Reputation must be separate from Battle Rating** — reputation earned from approved recipes, articles, likes, comments and consistency; rating from PvP. The document gives the reason: *"a chef can be a strong content creator without being the best PvP fighter."* | `tz_main.md` §9, `artifact_3` §9 | **The separation exists in the schema and nowhere else.** Both fields exist; reputation is written in exactly three places and every one is a battle outcome — `+15` on a win, `+7` on second place, `−5` on a refusal. **No recipe, article, like or comment ever moves it.** Content grants battle MOVES, not reputation, so the two ladders the ТЗ separates on purpose are both driven by PvP alone. |
| **G7** | The Board of Memory — the first twenty chefs to participate | `hall_of_fame.md` | Not built; the page shows a wins leaderboard instead. See 8.2. |
| **G8** | Rating affected by **opponent strength** and **repeated-opponent reduction**; §16's **diminishing returns vs a repeated opponent** | `tz_main.md` §9/§16, `artifact_3` §9 | Not built. A win is a flat `+25` whoever was beaten, and the only repeat control is a 24-hour cooldown on the same pair — a block, not a diminishing return. Beating the same weak opponent daily pays exactly what beating the champion pays. |
| **G9** | `BattleMoveTransaction.balance_after` | `tz_main.md` §17.7 | Absent. The **token** ledger carries `balance_after` and can be reconciled against the wallet; the **moves** ledger cannot. Nothing can prove today's move balance is the sum of its own history. |
| **G10** | `SeasonStanding.wins / losses / streak` | `tz_main.md` §17.13 | Absent — a standing row carries `score` and `rank_position` only, so a season leaderboard cannot show a chef's record for that season. |
| **G11** | `Season.crown_rule`, `Season.reward_rules_json` | `tz_main.md` §17.12 | Absent. Season rewards live in `season_service.py`, so changing a season's rules is a deploy rather than a data edit. |
| **G12** | `Battle.season` | `tz_main.md` §17.3 | Absent. A battle carries no season; standings are computed from the season's date window. It works, and it means a battle can never be reassigned and a season never re-run. |
| **G13** | Pages: battle **history**, a per-season page `/season/<slug>/`, a **crown-holder** page, a dedicated **vote-review** page | `tz_main.md` §18 | Absent as pages. Vote review exists in the Django admin (`is_suspicious` filter and two actions); the season page is one leaderboard with no per-season URL; the crown appears on the arena, not on a page of its own. |

### 8.4 Disagreements settled the way he ruled — the code is the decision

| ID | Subject | The document said | The code says | Note |
|---|---|---|---|---|
| **X19** | Starting rating | `battle_rating` **default 1000** (`artifact_3` §2) | `rating = IntegerField(default=0)` | The consequence is worth knowing: `penalise()` floors rating at zero, so a chef starting at 0 cannot lose rating at all, and the withdrawal penalty of "up to 15 rating" takes nothing from a new account. That behaviour is already on record; this is where it comes from. |
| **X20** | The second rung's public name | **Prep Cook** (`tz_main.md` §10) | Displays **"Prep Chef"** (value `prep_cook`) | The stored value is the document's; the label a chef reads is not. |
| **X21** | The arena's ring structure | 13 contiguous rings — centre, 8 ranks, `spectator_1..4` (`arena_data_layer_spec.md` §1) | The 11-ring octagon (Crown, Moat, 8 ranks, VIP), and spectators on an **oval** rather than polar rings — his own decisions of 2026-07-24 and 2026-07-29 | The spec predates both and was never updated. |
| **X22** | `center.type = "facing_pair"` | A pre-combat facing state (`arena_data_layer_spec.md` §3) | **Never produced.** `_arena_center()` refuses any battle that has not begun, so the type cannot occur; `arena_render.js:1843` still branches on it | A dead branch, one line. |
| **X23** | Clans dropped | `cuisines_design.md` header | `clans_alliances_rules.md` is later and builds clans **on** factions; the code agrees | The supersede line is the stale side. |

### 8.5 Where this leaves the corpus

All eighteen game-rule documents and `tz_main.md` have now been read against the
code. Across the whole corpus: **nine rules that were never built** (G1, G3, G6,
G7, G8–G13), **twelve disagreements settled in the code's favour** (X12–X23), and
**three findings of mine withdrawn or corrected** (G2, G4, X16) — plus 3.7,
which took two corrections before it was right.

The largest single item is **G6**. Everything else on the absence list is a
field, a page or a weighting. G6 is a product idea: the ТЗ builds two ladders on
purpose, explains why in its own words, and only one of them was built.

---

## 9. Closed on his order, 2026-08-11 — «нет, чиним, правим, работаем!»

Four items from this act, shipped together as **v2.5.997**. Bolt closed F1–F11,
T1 and T2 in v2.5.988, v2.5.994 and v2.5.996 in parallel, so the whole audit —
his and mine — is now either fixed or on the list below.

| Was | Now |
|---|---|
| **G6** — reputation moved only on battle outcomes, so the two ladders the ТЗ separates on purpose were both PvP-driven | Published recipes, articles, pinches and likes now pay **Culinary Reputation**, credited from inside `award_moves()` at the point that function already reserves for side-rewards: past the anti-farm and once-per-object gates, so a farmed like pays no status either, and **before** the energy cap, because a chef whose move balance is full has still earned what they published. **The three numbers are mine, not his** — recipe 3, article 3, like 1, anchored to the 15 a battle win pays. One constant each. |
| **G7** — the Board of Memory was a top-twenty-by-wins leaderboard | It is now the **first twenty chefs ever to fight, in arrival order**, taken from each chef's earliest battle by `created_at`. A place is earned by turning up; nothing later can take it. The page says so, and the leaderboard it used to duplicate already exists at `/rankings/`. |
| **G4's second half** — the Founding Ten were evicted by any later write, because the order came from `updated_at` (`auto_now`) | Ordered by the **BATTLE_FINISHED event**, whose `created_at` is `auto_now_add` and cannot move — which is also the truthful order, when each battle actually finished rather than when its row was last touched. A test moderates a battle after the fact and proves it keeps its seat. |
| **G1** — one slot per chef, enforced nowhere | `slot_occupied_reason()` enforces it **in full**: the slot is taken from the moment a challenge is **issued**, and an occupied slot refuses **accepting** as well as issuing. It frees when the challenge expires or the battle ends. Wired into both `challenge_create` and `challenge_respond`. |
| **X14** — `RARITY_TOKEN_COST` was referenced by nothing, so a new Epic cost 10 | `Artifact.save()` prices a **new** row from its rarity when nobody priced it. Deliberately narrow: create only, default only, and never a reprice — an explicit price stays the Owner's lever and no existing row is touched. |

**Still open, and all of it his:** G3 (artifact tier by cooking format — the
field does not exist), G8 (opponent strength and diminishing returns in the
rating), G9 (`balance_after` on the moves ledger), G10–G12 (season fields), G13
(four pages), and X15/X20's cosmetic labels. Every one is «будем строить» or a
weighting, not a defect.

### 9a. Second wave, v2.5.999 — «бери следующие: G8, G9, G10, G12»

| Was | Now |
|---|---|
| **G8** — a win paid a flat 25 whoever was beaten; the only repeat control was a 24-hour block on the pair | `rating_award_for_win()` multiplies the flat award by **strength** (from the rating gap, bounded 1.5×–0.5× across 500 points) and by **repeat** (halving per earlier win over the same chef inside 90 days, floored at a quarter), never below 1. **The five numbers are mine.** Nothing moves today: every chef on production sits at 0 rating, so the multiplier is exactly 1.0 and a test pins that. `Battle.rating_delta_*` — on the model since the beginning, never written — is populated too, now that the award is no longer a constant anybody can infer. |
| **G9** — the moves ledger had no `balance_after`, so it could not be reconciled the way the token ledger can | Both the award and the spend path record it, **read back from the database** after the update rather than computed in Python — the increment is capped and can land beside a concurrent one, and an arithmetic guess would record a balance the row never held. NULL on rows written before today, because an honest gap beats a plausible fiction. |
| **G10** — a standing carried a score and a position, so a leaderboard could rank chefs and never say what they did | `close_season()` freezes **wins, losses and the longest streak inside that season**, counted from the season's own battles rather than copied from the lifetime counters, which keep rising afterwards. Withdrawals, voids and cancellations count as neither. |
| **G12** — no battle carried a season; standings were derived from a date window | Stamped in `Battle.save()` on insert only and never rewritten, so the record survives a later edit to the calendar. NULL before today and when no season is active — both honest, neither guessed. The season counter reads the stamp first and falls back to the window only for unstamped rows. |

**This release carries migration 0086**, stated plainly because §8 excludes
migrations from the standing authorisation: three of the four cards he named
*are* fields. Additive only, every column nullable or defaulted, nothing
backfilled, nothing dropped — `migrate chef_battle 0085` reverses it.

**What is left of the whole audit:** G3 (artifact tier by cooking format —
«будем строить»), G11 (`crown_rule` / `reward_rules_json` on Season), G13 (four
pages), and two cosmetic labels. Nothing else.
