# ARTIFACT 2 — Phase 0 + Phase 1 Backlog / Ticket List

## Project: Chef’s Battle / CHEF Combats

This backlog is structured for practical implementation.

Recommended branch:

```text
feature/chef-battle-phase-1
```

Recommended Django app:

```text
chef_battle
```

---

# PHASE 0 — Foundation & Architecture

## Goal

Prepare the Chef’s Battle system as a clean, production-safe Django feature without building the full game engine yet.

---

## EPIC 0.1 — Create Django app foundation

### Ticket CB-0001 — Create `chef_battle` Django app

**Priority:** Critical
**Type:** Backend foundation

### Scope

Create a new app:

```text
chef_battle
```

Add base files:

```text
chef_battle/
  __init__.py
  admin.py
  apps.py
  models.py
  urls.py
  views.py
  selectors.py
  services/
    __init__.py
    challenge_service.py
    battle_service.py
    vote_service.py
    rating_service.py
    event_service.py
  templates/chef_battle/
  tests/
```

### Acceptance criteria

* App exists.
* App can be added to `INSTALLED_APPS`.
* `python manage.py check` passes.
* No behaviour changes outside the new app.

---

## EPIC 0.2 — Define core models

### Ticket CB-0002 — Implement `ChefBattleProfile`

**Priority:** Critical
**Type:** Backend / Models

### Fields

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

### Acceptance criteria

* One battle profile per user.
* Default rating is set.
* Default rank is set.
* Admin can view/search profiles.
* Tests cover profile creation.

---

### Ticket CB-0003 — Implement `BattleChallenge`

**Priority:** Critical
**Type:** Backend / Models

### Fields

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

### Statuses

* pending
* accepted
* refused
* expired
* cancelled

### Acceptance criteria

* Challenge cannot have same challenger and opponent.
* Pending challenge has expiry.
* Status transitions are testable.
* Admin list has filters by status/date.

---

### Ticket CB-0004 — Implement `Battle`

**Priority:** Critical
**Type:** Backend / Models

### Fields

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

### Statuses

* scheduled
* active
* awaiting_submissions
* revealed
* voting
* completed
* cancelled
* disputed

### Acceptance criteria

* Battle links to challenge.
* Battle stores both participants.
* Battle status lifecycle is testable.
* Battle cannot have winner before completion unless service allows it.

---

### Ticket CB-0005 — Implement `BattleEntry`

**Priority:** Critical
**Type:** Backend / Models

### Fields

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

### Rules

* One entry per chef per battle.
* Entry author must be one of battle participants.
* Entry should point to recipe or article.
* Hidden until reveal.

### Acceptance criteria

* Duplicate entry blocked.
* Invalid author blocked.
* Admin can inspect entries.
* Tests cover valid/invalid entries.

---

### Ticket CB-0006 — Implement `BattleVote`

**Priority:** Critical
**Type:** Backend / Models

### Fields

* battle
* voter_user
* voted_for
* ip_hash
* user_agent_hash
* session_key_hash
* created_at
* is_suspicious
* moderation_note

### Rules

* One vote per user per battle.
* Cannot vote for yourself.
* Cannot vote before reveal.
* Cannot vote after deadline.

### Acceptance criteria

* Unique constraint prevents duplicate votes.
* Self-vote is blocked.
* Vote timestamps stored.
* Admin can review votes.

---

### Ticket CB-0007 — Implement `BattleEvent`

**Priority:** High
**Type:** Backend / Models

### Fields

* battle
* event_type
* actor
* target
* message
* payload_json
* is_public
* created_at

### Event types

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

### Acceptance criteria

* Events can be public or private.
* Event message is human-readable.
* Events are ordered by date.
* Public events can be reused for homepage/activity feed.

---

## EPIC 0.3 — Service layer

### Ticket CB-0008 — Implement `challenge_service`

**Priority:** Critical
**Type:** Backend / Business logic

### Required functions

* create_challenge()
* accept_challenge()
* refuse_challenge()
* expire_challenge()
* cancel_challenge()
* validate_challenge_eligibility()

### Acceptance criteria

* No challenge lifecycle logic lives directly in views.
* Invalid transitions are blocked.
* Challenge events are created.
* Tests cover all transitions.

---

### Ticket CB-0009 — Implement `battle_service`

**Priority:** Critical
**Type:** Backend / Business logic

### Required functions

* create_battle_from_challenge()
* submit_entry()
* reveal_battle()
* complete_battle()
* cancel_battle()
* resolve_no_show()

### Acceptance criteria

* Battle creation is atomic.
* Entry submission is validated.
* Reveal logic works.
* Completion updates stats.
* Tests cover happy path and failure paths.

---

### Ticket CB-0010 — Implement `vote_service`

**Priority:** Critical
**Type:** Backend / Business logic

### Required functions

* cast_vote()
* validate_vote()
* get_vote_totals()
* flag_suspicious_vote()

### Acceptance criteria

* Duplicate vote blocked.
* Self-vote blocked.
* Voting only allowed during voting window.
* Tests cover all vote rules.

---

### Ticket CB-0011 — Implement `rating_service`

**Priority:** High
**Type:** Backend / Business logic

### Required functions

* calculate_rating_delta()
* apply_battle_result()
* apply_refusal_penalty()
* update_rank()
* award_crown_if_applicable()

### Acceptance criteria

* Winner gains points.
* Loser loses points.
* Refusal changes reputation.
* Crown can be assigned.
* Tests cover rating changes.

---

### Ticket CB-0012 — Implement `event_service`

**Priority:** High
**Type:** Backend / Business logic

### Required functions

* create_battle_event()
* create_public_news_event()
* get_public_battle_events()
* get_profile_battle_events()

### Acceptance criteria

* Events are created for major state transitions.
* Public events are queryable for homepage/profile/battle page.
* No duplicated event spam.

---

## EPIC 0.4 — Admin and internal tools

### Ticket CB-0013 — Register models in Django Admin

**Priority:** High
**Type:** Admin

### Acceptance criteria

* Admin can inspect challenges, battles, entries, votes and events.
* Filters by status/date/user exist.
* Search by chef/theme exists.
* Read-only timestamps are protected.

---

### Ticket CB-0014 — Add admin actions

**Priority:** Medium
**Type:** Admin

### Actions

* cancel battle
* mark vote suspicious
* force reveal battle
* force complete battle
* reset disputed battle

### Acceptance criteria

* Admin actions use service layer.
* Admin actions create events.
* Dangerous actions require clear naming.

---

# PHASE 1 — MVP Battle System

## Goal

Deliver the first public working version of Chef’s Battle.

Core loop:

```text
challenge → accept/refuse → battle room → submission → reveal → vote → result → rating → crown → public news
```

---

## EPIC 1.1 — Challenge creation flow

### Ticket CB-1001 — Build challenge creation form

**Priority:** Critical
**Type:** Frontend / Backend

### Fields

* opponent
* battle theme
* message
* battle type

### Acceptance criteria

* Logged-in eligible author can create challenge.
* Opponent cannot be self.
* Opponent must be eligible.
* Form validates empty/invalid values.
* Challenge created with pending status.
* Public/private event created.

---

### Ticket CB-1002 — Build incoming/outgoing challenges page

**Priority:** High
**Type:** Frontend

### Acceptance criteria

* User sees incoming pending challenges.
* User sees outgoing pending challenges.
* Challenge status is visible.
* Accept/refuse links available for incoming challenges.

---

### Ticket CB-1003 — Challenge accept/refuse view

**Priority:** Critical
**Type:** Backend / Frontend

### Acceptance criteria

* Opponent can accept.
* Opponent can refuse.
* Other users cannot respond.
* Accept creates battle.
* Refuse records refusal.
* Events are created.
* Stats update if required.

---

## EPIC 1.2 — Battle room

### Ticket CB-1101 — Public battle room template

**Priority:** Critical
**Type:** Frontend

### Must display

* battle title
* battle theme
* challenger
* opponent
* ranks
* status
* timer
* submission state
* vote totals after reveal
* result if completed
* battle events/log

### Acceptance criteria

* Page works for active battle.
* Page works for revealed battle.
* Page works for completed battle.
* Page is responsive.
* Page does not expose hidden submissions before reveal.

---

### Ticket CB-1102 — Timer and state display

**Priority:** High
**Type:** Frontend / Backend

### Acceptance criteria

* Submission deadline visible.
* Voting deadline visible after reveal.
* Expired status shown correctly.
* Server remains source of truth.
* Frontend timer is cosmetic, not authoritative.

---

## EPIC 1.3 — Battle entry submission

### Ticket CB-1201 — Entry submission form

**Priority:** Critical
**Type:** Frontend / Backend

### User can submit

* existing recipe
* existing article
* short battle statement

### Acceptance criteria

* Only battle participants can submit.
* Only own content can be submitted.
* Only approved/published content can be submitted.
* One entry per participant.
* Entry is hidden until reveal.
* Submitted event is created.

---

### Ticket CB-1202 — Hidden submission / reveal logic

**Priority:** Critical
**Type:** Backend

### Acceptance criteria

* Entries are hidden before reveal.
* Entries reveal when both are submitted or deadline passes.
* No hidden content leaks through templates.
* Tests confirm hidden state.

---

## EPIC 1.4 — Voting system

### Ticket CB-1301 — Vote panel

**Priority:** Critical
**Type:** Frontend / Backend

### Acceptance criteria

* Authenticated users can vote after reveal.
* Battle participants cannot vote in their own battle.
* One vote per user.
* Vote totals update.
* Voting closes after deadline.

---

### Ticket CB-1302 — Vote validation and anti-abuse v1

**Priority:** Critical
**Type:** Backend

### Acceptance criteria

* Duplicate votes blocked.
* Self-votes blocked.
* Votes outside allowed window blocked.
* Suspicious metadata can be stored.
* Tests cover abuse cases.

---

## EPIC 1.5 — Result calculation

### Ticket CB-1401 — Complete battle by public vote

**Priority:** Critical
**Type:** Backend

### Acceptance criteria

* Winner determined by vote total.
* Draw handling exists.
* Winner/loser stored.
* Battle status becomes completed.
* Result reason stored.
* Stats updated.

---

### Ticket CB-1402 — No-show and late submission handling

**Priority:** High
**Type:** Backend

### Acceptance criteria

* One missing entry can cause default loss.
* Both missing entries can cancel/expire battle.
* Late status stored.
* Public event created.

---

### Ticket CB-1403 — Rating and rank update

**Priority:** High
**Type:** Backend

### Acceptance criteria

* Winner rating increases.
* Loser rating decreases.
* Streaks update.
* Rank updates if threshold crossed.
* Rank promotion event created.

---

### Ticket CB-1404 — Crown holder v1

**Priority:** High
**Type:** Backend / Frontend

### Acceptance criteria

* Winner receives 24h crown.
* Crown visible on profile/battle views.
* Crown event created.
* Expired crown no longer displays.

---

## EPIC 1.6 — Site-wide visibility

### Ticket CB-1501 — Battle landing page

**Priority:** High
**Type:** Frontend

### Must show

* active battles
* recent completed battles
* crown holder
* top chefs
* call-to-action to challenge

### Acceptance criteria

* Public visitor can view.
* Logged-in author gets CTA.
* Page feels like a live battle hub.

---

### Ticket CB-1502 — Homepage battle news integration

**Priority:** High
**Type:** Frontend / Backend

### Acceptance criteria

* Completed battle appears as public news/activity.
* Crown event appears.
* Challenge accepted/started can appear if public.
* Feed does not spam too many events.

---

### Ticket CB-1503 — Chef profile battle stats block

**Priority:** Medium
**Type:** Frontend / Backend

### Must show

* rank
* rating
* wins
* losses
* refused battles
* crown status
* recent battles

### Acceptance criteria

* Existing profile page remains stable.
* Stats block is visible only where appropriate.
* No performance-heavy queries.

---

## EPIC 1.7 — Tests and quality gate

### Ticket CB-1601 — Model and service tests

**Priority:** Critical
**Type:** Tests

### Required coverage

* profile creation
* challenge create/accept/refuse
* battle creation
* entry submission
* reveal
* voting
* result
* rating
* crown

---

### Ticket CB-1602 — Permission tests

**Priority:** Critical
**Type:** Tests

### Required coverage

* anonymous cannot create challenge
* non-participant cannot submit
* participant cannot vote
* user cannot respond to someone else’s challenge
* hidden entries are not visible before reveal

---

### Ticket CB-1603 — Regression checks

**Priority:** Critical
**Type:** QA

### Commands

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test chef_battle
python manage.py test
git diff --check
```

---

# Phase 1 Definition of Done

Phase 1 is complete only when:

1. A chef can challenge another chef.
2. Opponent can accept/refuse.
3. Accepted challenge creates Battle Room.
4. Both chefs can submit entries.
5. Entries remain hidden until reveal.
6. Visitors can vote after reveal.
7. Battle can complete.
8. Winner/loser are stored.
9. Rating and stats update.
10. Crown can be awarded.
11. Public battle news/event appears.
12. Admin can inspect and intervene.
13. Tests pass.
14. No unrelated system is broken.
