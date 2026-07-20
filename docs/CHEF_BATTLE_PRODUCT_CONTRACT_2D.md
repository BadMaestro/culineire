# Chef Battle Product Contract — 2D

```yaml
document:
  id: "chef-battle-product-contract-2d"
  version: "1.0.0"
  status: "ACTIVE_AFTER_OWNER_MERGE"
  owner: "CulinEire Product Owner"
  canonical_path: "/docs/CHEF_BATTLE_PRODUCT_CONTRACT_2D.md"
  last_updated: "2026-07-20"
```

## 1. Product definition

Public name: **Chef Battle**  
Internal system name: **CHEF Combats Engine**

Chef Battle is not a simple recipe contest. It is a production-grade culinary
competition, retention, status, and creator-engagement system inside CulinEire.

Its purpose is to turn recipes, articles, chef identity, audience participation,
and public events into a living competitive layer of the existing site.

The core promise is:

```text
The battle must sound across the site.
```

Important battle events must be reusable by the homepage, profiles, battle
history, notifications, moderation, and public activity surfaces.

## 2. Current implementation strategy

- Keep the existing Django monolith.
- Keep the existing `chef_battle` domain and data layer.
- Reuse existing backend contracts.
- Do not build a second Chef Battle system.
- Do not introduce a microservice or heavy SPA.
- Use the existing templates, CSS architecture, and JavaScript where valid.
- Replace or adapt only the presentation boundary proven to belong to the abandoned Arena direction.
- Implementation is incremental and feature-flagged where risk requires it.

## 3. Core battle loop

The protected product loop is:

```text
challenge
→ accept / refuse / expire
→ battle creation
→ readiness and phase control
→ hidden entry submission
→ combat and ingredient rules where enabled
→ cooking and real-photo evidence
→ moderation
→ reveal
→ protected public voting
→ result
→ rating and statistics
→ 24-hour crown
→ site-wide events
```

Existing domain rules, statuses, transitions, deadlines, permissions, scoring,
rating, crown, rewards, ledgers, events, and moderation remain server authoritative.

The frontend must display server state and delegate actions. It must not
recalculate winners, infer hidden phases, reproduce eligibility rules, reveal
protected content, mint rewards, or bypass moderation.

## 4. Product surfaces

Chef Battle uses three distinct interface surfaces.

### 4.1 Arena Hall

Purpose:

- discover active and upcoming battles;
- show rankings, ranks, Crown Holder, status, metrics, and entry points;
- enable appropriate profile and challenge actions;
- provide an understandable overview of the competitive world.

Direction:

- responsive 2D;
- normal document flow;
- no camera simulation;
- no photographic backdrop matching;
- no generated crowd requirement;
- no independent dark esports visual system.

### 4.2 Battle Room / Battle Broadcast

Purpose:

- represent one battle;
- show the two chefs, theme, phase, timers, allowed actions, battle state,
  ingredients and tactical state where enabled;
- handle submission, moderation state, reveal, voting, result, gifts, reactions,
  chat, or broadcast information only when the relevant feature is enabled;
- preserve secrecy and permissions.

This surface may use canonical navigation, an embedded presentation, or both only
after the Product Owner approves the exact interaction contract.

### 4.3 Arena Master Console

Purpose:

- staff and operator control;
- moderation;
- governance;
- safety and visibility controls;
- battle and broadcast supervision.

It is not the public Arena.

The existing shared renderer dependency must not be removed until the Master
Console is decoupled or receives a compatible replacement.

## 5. Pre-release access

Chef Battle Arena is currently being developed on production and is **not publicly released**.

Until a separate explicit Product Owner release decision:

```yaml
arena_visibility:
  staff: true
  superuser: true
  ordinary_authenticated_user: false
  recipe_author_without_staff: false
  anonymous: false
```

No code capability, test, feature flag, or historical document constitutes release approval.

If production behaviour differs, treat it as a release-gate defect. Verify and
correct it under a separately approved, tested task.

## 6. Core entities and contracts

The existing codebase is authoritative for exact current field names and
migrations. Conceptually protected entities include:

- Chef Battle profile and eligibility;
- challenge;
- battle;
- entry/submission;
- vote;
- battle event;
- rank and rating;
- Crown Holder;
- battle moves;
- ingredient locks and tactical combat actions where enabled;
- artifacts and inventory;
- token account and token ledger;
- gifts;
- reward records;
- moderation and disputes;
- notifications;
- viewer presence and metrics;
- Live Arena snapshot where enabled;
- payout preparation where enabled.

Before changing a schema or contract, trace all consumers and existing tests.

## 7. Battle integrity

The following are non-negotiable:

- no self-challenge;
- no participant voting in their own battle;
- duplicate-vote protection;
- server-authoritative eligibility;
- hidden entries remain inaccessible until authorised reveal;
- both entries follow the approved reveal contract;
- suspicious voting can be reviewed;
- bot voting, vote buying, paid voting, collusion, and coordinated manipulation are prohibited;
- result calculation is idempotent;
- rating, crown, reward, and ledger changes are transactional and auditable;
- staff can pause, dispute, void, review, or sanction according to approved rules;
- audit evidence required for fraud, accounting, payout, or legal retention is not deleted.

## 8. Eligibility and age

Author status does not automatically create Chef status.

Chef status is a separately approved state for battle participation.

Battle participation, paid tokens, paid gifts, artifacts, payout-eligible reward
records, Stripe Connect onboarding, payout requests, and Live Video are
restricted to users aged 18 or over.

Chef approval may require:

- accepted rules;
- profile data;
- eligibility and battle-move conditions;
- fraud and compliance checks;
- reward or payout verification where applicable;
- staff/admin approval.

Staff may approve, delay, suspend, reject, or revoke Chef eligibility.

## 9. Tokens, gifts, artifacts, and rewards

### 9.1 Spendable Tokens

CulinEire Tokens / Spendable Tokens / `T` are closed-loop internal digital credits.

They:

- are usable only inside CulinEire;
- have no cash value;
- are not e-money, a deposit, an investment, or a user fund;
- cannot be withdrawn;
- cannot be transferred user-to-user;
- cannot be sold or resold;
- cannot be used as a stake;
- cannot form a pot, jackpot, betting pool, or prize pool;
- cannot directly become CBR, LSR, or cash.

Use `TokenAccount`, `Token Balance`, `Token Ledger`, and `Token Transaction`
terminology. Do not introduce new wallet or cash-balance terminology.

### 9.2 Gifts

Appreciation Gifts and Battle Gifts are digital platform items.

Alcohol-themed gifts are symbolic digital reactions only. They are not physical
alcohol, delivery, prizes, discounts, or encouragement to consume alcohol.

A gift may create a separate pending LSR record only through explicit approved
platform logic. It is never a direct transfer of purchased tokens to a Chef.

### 9.3 Artifacts

Artifacts are digital combat items.

They:

- have no cash value;
- are not CBR or LSR;
- create no direct payout right;
- are not transferable or resellable between users;
- have no secondary market;
- must not become pay-to-win;
- are consumed according to the active combat rules when one-use.

Paid random loot boxes, paid mystery packs, chance-based cash-like rewards, or
similar mechanics require separate legal review and are not authorised by this contract.

### 9.4 CBR and LSR

CBR and LSR are internal reward records.

They are not money, user funds, debt, guaranteed earnings, or an automatically
withdrawable balance.

They may become payout-eligible only after the required unlock, fraud checks,
compliance review, verification, and admin approval.

Winning a battle does not automatically create a monetary payout.

## 10. Stripe, VAT, payouts, and legal controls

- Token purchases use Stripe Checkout.
- VAT/tax must be clearly disclosed and recorded.
- VAT is not reward money and must not enter reward calculations.
- Required consumer consent for immediate digital supply must be captured when applicable.
- Stripe Connect payouts remain disabled by default until legal, accounting,
  tax, compliance, and operational approval.
- Payouts are not automatic, instant, or guaranteed.
- DAC7/MRDP and Revenue reporting readiness is an operational requirement before payout activation.
- No gambling, betting, staking, jackpot, user-funded prize pool, or token wager may be introduced.
- Accounts are personal and non-transferable.
- The legal/product pack is a professional-review draft unless and until the
  company completes approval and signing. Legal or tax uncertainty must be escalated, not guessed.

## 11. AI content, evidence, moderation, and Live Video

- AI-related content must follow the active AI governance and disclosure rules.
- Chef Battle cooking evidence must follow the real-photo and moderation rules.
- Copyright, image rights, food-safety presentation, allergens, and forbidden claims must be respected.
- Live Video Round 2 remains disabled unless provider-level safety, moderation,
  delay, kill switch, privacy, child-safety, and operational readiness are approved.
- A staff/admin kill switch is mandatory before live activation.
- Users must be able to report abuse, fraud, manipulation, unsafe content,
  copyright problems, and live-safety breaches.
- Moderation actions must preserve required audit history.

## 12. Arena 2D presentation contract

The public Arena must:

- use the official CulinEire design system;
- use existing tokens;
- use warm parchment, natural ink, muted bronze, and soft neutral surfaces;
- use existing Playfair Display and Inter typography;
- be semantic, responsive, accessible, keyboard-operable, and reduced-motion aware;
- have explicit loading, empty, hidden, unauthorised, error, and active states;
- keep challenger-left and opponent-right as semantic placement only, without mandating raw green/red panels;
- preserve backend payload and action contracts;
- avoid duplicate JavaScript listeners and duplicate selectors.

The public Arena must not be defined by:

- 3D perspective;
- `rotateX`;
- camera angles;
- photographic hall alignment;
- projector or billboard fitting;
- generated spectator crowds;
- raw mockup-sampled colours;
- independent dark game styling;
- hard-coded coordinate choreography.

## 13. Protected existing dependencies

- Do not remove `_arena_render_ring.html` until every consumer, including the Arena Master Console, is decoupled or has a compatible replacement.
- Do not delete suspected legacy renderer files or assets during the first 2D implementation.
- Six overlapping Arena stylesheets are consolidation candidates, not automatic deletion candidates.
- `arena_battle_room.js` requires accessibility and focus review before being treated as reuse-without-change.
- The confirmed initial binding issue involving `crown_streak`, `crown_ladder`, and `recent_gifts` is a separate tested defect task.
- No old file is considered confirmed dead merely because no simple grep caller was found.

## 14. Release gates

No public release until the Product Owner explicitly approves it.

A release decision requires evidence for:

- access policy;
- responsive behaviour;
- keyboard and screen-reader use;
- reduced motion;
- state and action parity;
- vote and reveal integrity;
- moderation;
- production migration readiness;
- staff console compatibility;
- feature flags;
- legal/accounting gates for any economy or payout feature;
- rollback.

## 15. Product decisions still requiring task-level approval

The Product Owner will decide, in the relevant execution plan:

- canonical Battle Room navigation, embedded presentation, or both;
- whether the privileged Live Arena visual preview remains;
- the exact 2D information hierarchy;
- responsive and accessibility acceptance matrices;
- timing of the context-binding defect fix;
- timing of the later legacy-deletion audit;
- public release and post-release audience access.
