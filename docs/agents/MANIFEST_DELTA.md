# Manifest vs. reality — read this before following either manifest literally

`CHEF_COMBATS_MANIFEST.md` and `CLAUDE_RULES.md` in this folder were written
before a large part of `chef_battle` existed. Read code-checked on 2026-07-20
against both documents and found five places where following the manifest
literally would either halt useful work or actively regress production. The
owner ruled on each one. Read this file before either manifest changes your
behavior — a rule the owner already overrode is not a rule.

| # | Manifest says | Code reality (2026-07-20) | Owner's ruling |
|---|---|---|---|
| 1 | §6: "Do not build advanced modules early... FUTURE PHASES: Do not write code for these yet!" (energy economy, attack/block combat, artifacts/inventory) | Already live in production: `TokenPackage`/`TokenWallet`/Stripe (`chef_battle/stripe_services.py`), `BattleCombatAction`/`IngredientLock`/`IngredientShot` (tactical combat), `Artifact`/`ChefArtifact`/`CosmeticItem`, plus `Season`/`Faction`/`Clan` (not even mentioned in the manifest) | **Manifest is stale. Do not roll any of it back.** §2 and §6 do not apply going forward. |
| 2 | §2: work splits into Track A (schema/models/admin/migrations only) and Track B (services/selectors/views only), neither may touch the other's files | We split by layer instead: Bolt owns backend (`chef_battle/*.py`, `recipes/views.py`, `presence/`, `accounts/`), GB owns frontend (`static/css/arena*.css`, `static/js/arena*.js`, `templates/chef_battle/arena*.html`) | Track A/B split does not apply. Layer split in `docs/agents/README.md` is the real one. |
| 3 | CLAUDE_RULES §2: "Neither of you is the manager. You are equal feature engineers." | Prior protocol had GB as a Junior Front End Developer in MANUAL mode, waiting on Bolt's explicit order | **In force, as of 2026-07-20.** The MANUAL/Junior protocol is retired. Neither agent gives the other orders; work is claimed from the board and coordinated by file-boundary agreement, not command. |
| 4 | §1: "Use Django Templates + HTMX for instant dynamic interaction, and Alpine.js for lightweight UI state management." | Zero occurrences of `htmx`, `x-data`, or `alpine` anywhere in the project. All dynamic frontend is vanilla JS (`arena_render.js` alone is 1000+ lines) | **Not adopted.** Frontend stays vanilla JS. Do not introduce HTMX or Alpine to satisfy this line. |
| 5 | §4: "Dark Premium Culinary UI... Layout Structure: Elite esports match layout" implies a dark arena floor | Owner decision, standing: the arena floor is light parchment; dark is scoped to the spectator stands only ([[feedback_arena_floor_light]]) | **Owner's floor-colour decision outranks this manifest line.** **SUPERSEDED 2026-07-20 (Arena 2D audit closure):** §4's dark stands, mockup-sampled hex palette, and "elite esports" dark-premium direction are not active 2D requirements — see `docs/ai/audits/arena_2d/SHARED/CURRENT_ARENA_SOURCE_OF_TRUTH.md`. Challenger-left/opponent-right is retained as a **semantic placement concept**, not a mandate for raw green/red/black/gold hex values — any 2D colour must come from the official CulinEire design tokens (`--brand`, `--ink`, existing semantic tokens), never from a mockup sample or a new raw literal. |

## What the manifest got right, and where it's actually being applied

Confirmed by code read, not assumed:

- **§3.1 (self-vote must be blocked at DB level, not just services):** was true and unenforced — `BattleVote.clean()` existed but Django never calls `clean()` from `save()`, so nothing in the database actually stopped it. Fixed 2026-07-20: `voter_author` field + `CheckConstraint`, migration `0083`. See build board stage `integrity`.
- **§3.3 (vote hashes must be salted):** was true — `hash_request_value` was a bare `hashlib.sha256`, reversible for anything as small as an IPv4 address. Fixed same day: HMAC keyed on `SECRET_KEY`, versioned via `hash_scheme` so old rows aren't silently miscompared against new ones.
- **§3.2 (blind reveal, both entries flip together)** and **§3.5 (24h crown expiry)**: already correctly implemented (`services.py` `reveal_entries_if_ready`, `crown_until = now() + timedelta(hours=24)`). No action needed.
- **§4 (challenger green / opponent red)**: **superseded 2026-07-20** — see the
  row above and the note below. Only the semantic left/right placement
  concept survives; it is not a mandate for raw colour values or a dark
  design system.

## Current 2D visual-direction status (2026-07-20, Arena 2D audit closure)

The Arena 2D rebuild does not use this manifest's §4 as a design source.
Authoritative status:

- Dark stands/dark hall are **not** an active 2D requirement.
- Green challenger / red opponent panels are **not mandatory** — only the
  left/right semantic placement concept is retained.
- Colours sampled from the old mockup (see `docs/chef_battle/arena_mockup_spec.md`,
  now `HISTORICAL_CONCEPT_REFERENCE`) are **prohibited** as a source for any
  2D colour.
- Raw green/red/black/gold hex values must **not** be introduced for the 2D
  Arena.
- Existing approved semantic tokens may be reused **only** if they already
  exist in the official site design system (`base.css` `:root` tokens) —
  do not invent new ones to match old mockup colours.
- The official parchment, ink, and muted-bronze design system
  (`CulinEire_colour_font_scheme.pdf` + `:root` tokens) is authoritative for
  the 2D Arena, full stop.

See `docs/ai/audits/arena_2d/SHARED/CURRENT_ARENA_SOURCE_OF_TRUTH.md` for the
single current entry point this all traces back to.

## How to use this file

If a future session reads `CHEF_COMBATS_MANIFEST.md` or `CLAUDE_RULES.md` and is
about to halt work, refuse a file, or start an HTMX migration because of what
one of them says — check this table first. If the row isn't here, the manifest
line hasn't been checked against code yet; verify before acting, don't assume
either document is current.
