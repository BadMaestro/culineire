# ARTIFACT 1 — AI Developer Prompt for Claude / Codex

## Project: CulinEire Chef’s Battle / CHEF Combats

You are working on an existing Django production project called CulinEire.

Your role is to implement a new major product feature called **Chef’s Battle**. Internally, the feature may also be referred to as **CHEF Combats Engine**.

This is not a simple recipe contest. It is a gamified culinary PvP system inspired by old browser-based MMORPG mechanics, adapted for a modern recipe, article and chef-author platform.

The feature must be implemented carefully, in phases, without breaking the existing production system.

---

## Existing stack assumptions

The project is a Django monolith.

Expected stack:

* Django
* Python 3.12
* PostgreSQL
* Django templates
* existing CSS/design system
* existing author/user system
* existing recipes/articles system
* existing newsfeed/activity functionality
* existing server deployment flow
* existing test suite

Do not introduce a separate service, SPA rewrite, or unnecessary microservice architecture.

The correct implementation direction is:

**new Django app + clean service layer + tests + progressive enhancement.**

Suggested app name:

```text
chef_battle
```

---

## Product goal

Create a retention engine for CulinEire.

Chef’s Battle should allow chefs/authors to challenge each other publicly, submit recipes or articles, compete under a theme, receive public votes, gain rating, build reputation, win titles, hold a crown, appear in site-wide activity, and eventually use earned battle moves, artifacts and seasonal rankings.

The system must make the website feel alive.

Important principle:

**Every major battle event should create visible public activity across the site.**

Examples:

* challenge created
* challenge accepted
* battle started
* battle submission received
* battle revealed
* battle finished
* chef defeated another chef
* new crown holder
* rank promotion

---

## Non-negotiable product principles

1. Build this as a phased production-safe system.
2. Do not overcomplicate the MVP with the full combat engine.
3. MVP should focus on public challenge, battle room, 24h timer, hidden submissions, voting, result, rating, crown and homepage/news visibility.
4. Keep the system fair and resistant to abuse.
5. Avoid obvious pay-to-win mechanics.
6. Artifacts should be earned through gameplay, not directly bought.
7. Battle points / energy should eventually be earned through approved platform activity.
8. Public status is central: wins, losses, refused battles, ranks, streaks and crowns must be visible.
9. Battle activity must be reusable across homepage, profiles, battle history and notifications.
10. Keep UI clean, premium, readable and aligned with the CulinEire brand.

---

## Phase 0 scope — foundation only

Implement or prepare the following:

### 1. New Django app

Create a new Django app:

```text
chef_battle
```

Add it to installed apps only when ready.

### 2. Core model design

Create initial models for:

* ChefBattleProfile
* BattleChallenge
* Battle
* BattleEntry
* BattleVote
* BattleEvent

Do not implement artifacts, cosmetics, advanced combat rounds or seasons in Phase 0 unless explicitly requested.

### 3. Service layer

Create service modules:

```text
chef_battle/services/challenge_service.py
chef_battle/services/battle_service.py
chef_battle/services/vote_service.py
chef_battle/services/rating_service.py
chef_battle/services/event_service.py
```

Business logic should live in services, not directly in views.

### 4. Selectors

Create selectors for read queries:

```text
chef_battle/selectors.py
```

Use selectors for battle lists, profile stats, public battle page data and leaderboard data.

### 5. Admin registration

Register all MVP models in Django Admin with useful list displays, filters and search fields.

### 6. Tests

Create tests for:

* model creation
* challenge lifecycle
* accept/refuse/expire logic
* battle creation
* vote uniqueness
* self-voting protection
* basic result calculation
* rating update
* crown assignment

---

## Phase 1 MVP scope

Build the first usable version of Chef’s Battle.

### User-facing flow

1. A logged-in author can challenge another eligible author.
2. The challenger chooses:

   * opponent
   * battle theme
   * optional message
   * battle type
3. The opponent can:

   * accept
   * refuse
   * ignore until expiry
4. If accepted:

   * create a Battle
   * create public Battle Room
   * set 24h submission deadline
5. Both chefs submit an existing approved recipe or article as BattleEntry.
6. Entries remain hidden until both are submitted or until deadline.
7. After reveal, visitors can vote.
8. After voting window ends:

   * calculate winner
   * update wins/losses
   * update Battle Rating
   * update Culinary Reputation if required
   * assign 24h crown if applicable
   * create public BattleEvent/news entry
9. Public pages reflect the result.

---

## MVP pages

Create the following views/templates:

```text
/battle/
```

Battle landing page: active battles, recent results, crown holder, leaderboard preview.

```text
/battle/challenges/
```

Current user’s incoming/outgoing challenges.

```text
/battle/challenge/new/
```

Create challenge form.

```text
/battle/challenge/<id>/
```

Challenge detail page with accept/refuse actions.

```text
/battle/<battle_id>/
```

Public battle room.

```text
/battle/leaderboard/
```

Battle rating leaderboard.

```text
/battle/history/
```

Completed battle archive.

Optional later:

```text
/chef/<slug>/battle/
```

Chef battle profile block/page.

---

## Suggested MVP models

### ChefBattleProfile

Fields:

* user
* battle_rank
* battle_rating
* culinary_reputation
* wins
* losses
* refused_battles
* ignored_battles
* win_streak
* best_win_streak
* crown_until
* crown_count
* battle_moves
* seasonal_score
* created_at
* updated_at

### BattleChallenge

Fields:

* challenger
* opponent
* theme
* message
* battle_type
* status
* expires_at
* accepted_at
* refused_at
* cancelled_at
* created_at
* updated_at

Statuses:

* pending
* accepted
* refused
* expired
* cancelled

### Battle

Fields:

* challenge
* challenger
* opponent
* theme
* battle_type
* status
* start_time
* submission_deadline
* reveal_time
* voting_deadline
* end_time
* winner
* loser
* result_reason
* rating_delta_challenger
* rating_delta_opponent
* crown_awarded
* created_at
* updated_at

Statuses:

* scheduled
* active
* awaiting_submissions
* revealed
* voting
* completed
* cancelled
* disputed

### BattleEntry

Fields:

* battle
* author
* recipe
* article
* battle_statement
* submitted_at
* is_revealed
* is_late
* moderation_status
* created_at
* updated_at

Rules:

* one entry per chef per battle
* entry must belong to the submitting chef
* entry must be approved/published if using existing content
* hidden until reveal

### BattleVote

Fields:

* battle
* voter_user
* voted_for
* ip_hash
* user_agent_hash
* session_key_hash
* created_at
* is_suspicious
* moderation_note

Rules:

* no self-voting
* one vote per authenticated user per battle
* optional anonymous voting can be added later
* repeated votes must be blocked

### BattleEvent

Fields:

* battle
* event_type
* actor
* target
* message
* payload_json
* is_public
* created_at

Event types:

* challenge_created
* challenge_accepted
* challenge_refused
* challenge_expired
* battle_started
* entry_submitted
* battle_revealed
* vote_cast
* battle_finished
* chef_defeated
* crown_awarded
* rank_promoted

---

## Rating system v1

Use a simple, understandable rating system for MVP.

Initial rating:

```text
1000
```

Basic win/loss delta:

```text
Winner: +25
Loser: -15
```

Optional modifiers:

* stronger opponent defeated: extra bonus
* repeated same opponent: reduced gain
* refusal: small reputation penalty
* win streak: small bonus

Do not implement a complex ELO system unless requested.

The first version should be transparent and testable.

---

## Crown system v1

When a chef wins a qualifying battle:

* set `crown_until = now + 24 hours`
* increment `crown_count`
* show crown marker on profile and battle pages
* create `crown_awarded` BattleEvent
* show event on battle/homepage feed

If another chef wins a later qualifying battle, crown can transfer according to rules.

Keep the first version simple.

---

## Battle reveal rules

MVP recommended rule:

* If both chefs submit before deadline, reveal both entries immediately or at scheduled reveal time.
* If one chef submits and the other misses the deadline, mark missing chef as late/missed.
* If one chef fails to submit, opponent may win by default.
* If both fail to submit, battle expires/cancels with no winner.

Store result reason clearly:

* public_vote
* opponent_no_show
* admin_decision
* cancelled
* expired

---

## Voting rules

MVP:

* authenticated users only
* one vote per user per battle
* no self-voting
* cannot vote before reveal
* cannot vote after voting deadline
* cannot vote in own battle
* vote totals visible after reveal

Optional later:

* anonymous protected voting
* IP/session hashing
* anomaly detection
* vote moderation queue

---

## Anti-abuse rules for MVP

Implement at least:

1. Prevent duplicate votes.
2. Prevent self-voting.
3. Prevent challenge spam.
4. Add cooldown between same two chefs.
5. Prevent a user from having too many active outgoing challenges.
6. Only allow eligible authors/chefs to participate.
7. Only approved content can be submitted.
8. Admin can cancel/dispute a battle.
9. Suspicious votes can be flagged later.

---

## UI direction

The UI should feel like a premium dark culinary battle arena, not a cartoon or fantasy game.

Visual requirements:

* clean readable text
* strong chef vs chef layout
* battle theme visible
* timer visible
* status badges
* vote panel
* live/activity section
* crown/winner treatment
* restrained green/red competitive accents
* responsive design
* accessible controls

Do not introduce messy neon, fake fantasy elements, unreadable text or heavy animation.

---

## Tests required before completion

Run:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test chef_battle
python manage.py test
```

If full project test suite is too slow, explain what was run and why.

Also check:

```bash
git diff --check
```

If templates/static files changed, note whether `collectstatic` is required.

---

## Completion report format

When done, return:

```yaml
task: "Chef Battle Phase X"
status: "complete / partial / blocked"
branch: "<branch-name>"
commits:
  - "<hash> <message>"
changed_files:
  - "..."
migrations_required: true/false
collectstatic_required: true/false
tests_run:
  - command: "..."
    result: "PASS/FAIL"
manual_checks:
  - "..."
known_risks:
  - "..."
next_steps:
  - "..."
```

---

## Final reminder

The first release must not try to implement the entire future game system.

Phase 1 must deliver the core retention loop:

```text
challenge → accept/refuse → battle room → hidden submission → reveal → vote → result → rating → crown → public site event
```

Everything else must be built on top of that.
