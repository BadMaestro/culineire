# ARTIFACT 3 — Models, Statuses, Business Rules & Phase Map

## Project: Chef’s Battle / CHEF Combats

This document defines the core data structure, lifecycle statuses and business rules for the Chef’s Battle system.

---

# 1. Core model map

| Model                   | Purpose                                                                           | Phase | Public?             |
| ----------------------- | --------------------------------------------------------------------------------- | ----: | ------------------- |
| `ChefBattleProfile`     | Stores battle rank, rating, reputation, stats and crown state for each chef/user. |     1 | Partly              |
| `BattleChallenge`       | Stores challenge request from one chef to another.                                |     1 | Partly              |
| `Battle`                | Main battle entity created after accepted challenge.                              |     1 | Yes                 |
| `BattleEntry`           | Recipe/article submitted by each participant.                                     |     1 | Hidden until reveal |
| `BattleVote`            | User vote for one of the chefs.                                                   |     1 | Aggregated only     |
| `BattleEvent`           | Public/private event log for battle activity.                                     |     1 | Public if marked    |
| `BattleMoveTransaction` | Ledger for earned/spent battle energy/moves.                                      |     3 | Private/partial     |
| `Artifact`              | Earned gameplay item.                                                             |     5 | Yes                 |
| `ChefArtifact`          | Chef-owned artifact inventory.                                                    |     5 | Partly              |
| `CosmeticItem`          | Premium or earned cosmetic.                                                       |     5 | Yes                 |
| `ChefCosmetic`          | Chef-owned cosmetics.                                                             |     5 | Partly              |
| `Season`                | Competitive season definition.                                                    |     6 | Yes                 |
| `SeasonStanding`        | Seasonal leaderboard row.                                                         |     6 | Yes                 |
| `KitchenClan`           | Clan/kitchen/faction system.                                                      |     6 | Yes                 |
| `KitchenMembership`     | Chef membership in a clan/kitchen.                                                |     6 | Partly              |

---

# 2. ChefBattleProfile

## Purpose

Adds PvP/social progression to an existing user/author.

## Fields

| Field                 | Type idea         | Rule                    |
| --------------------- | ----------------- | ----------------------- |
| `user`                | OneToOne          | Required                |
| `battle_rank`         | CharField         | Default: Kitchen Porter |
| `battle_rating`       | Integer           | Default: 1000           |
| `culinary_reputation` | Integer           | Default: 0              |
| `wins`                | Integer           | Default: 0              |
| `losses`              | Integer           | Default: 0              |
| `refused_battles`     | Integer           | Default: 0              |
| `ignored_battles`     | Integer           | Default: 0              |
| `win_streak`          | Integer           | Default: 0              |
| `best_win_streak`     | Integer           | Default: 0              |
| `crown_until`         | DateTime nullable | Active crown if future  |
| `crown_count`         | Integer           | Number of crowns earned |
| `battle_moves`        | Integer           | Phase 3                 |
| `seasonal_score`      | Integer           | Phase 6                 |
| `created_at`          | DateTime          | Auto                    |
| `updated_at`          | DateTime          | Auto                    |

## Business rules

| Rule                           | Description                                                                  |
| ------------------------------ | ---------------------------------------------------------------------------- |
| Profile creation               | Battle profile should be created automatically or lazily for eligible users. |
| Rating cannot go below floor   | Example floor: 0 or 500 depending on design.                                 |
| Crown is time-based            | Crown displays only if `crown_until > now`.                                  |
| Rank derived from score/rating | Rank should be recalculated by service, not manually edited casually.        |
| Stats are service-updated      | Wins/losses/refusals should not be changed directly in views.                |

---

# 3. BattleChallenge

## Purpose

Represents a challenge before a battle exists.

## Statuses

| Status      | Meaning                                       | Allowed next states                   |
| ----------- | --------------------------------------------- | ------------------------------------- |
| `pending`   | Waiting for opponent response.                | accepted, refused, expired, cancelled |
| `accepted`  | Opponent accepted. Battle should be created.  | none                                  |
| `refused`   | Opponent refused.                             | none                                  |
| `expired`   | Opponent did not respond in time.             | none                                  |
| `cancelled` | Challenger/admin cancelled before acceptance. | none                                  |

## Business rules

| Rule                             | Description                                      |
| -------------------------------- | ------------------------------------------------ |
| No self-challenge                | Challenger and opponent cannot be the same user. |
| Eligibility required             | Both users must be eligible authors/chefs.       |
| Cooldown required                | Same pair cannot spam challenges repeatedly.     |
| Limit active outgoing challenges | Prevent harassment/spam.                         |
| Refusal is recorded              | Refusal can affect reputation.                   |
| Expiry should be automatic       | Use scheduled task or management command.        |

---

# 4. Battle

## Purpose

Main public duel entity after challenge acceptance.

## Statuses

| Status                 | Meaning                                  | Allowed next states                                 |
| ---------------------- | ---------------------------------------- | --------------------------------------------------- |
| `scheduled`            | Battle created but not active yet.       | active, cancelled                                   |
| `active`               | Battle is live and awaiting submissions. | awaiting_submissions, revealed, cancelled, disputed |
| `awaiting_submissions` | Participants must submit entries.        | revealed, completed, cancelled, disputed            |
| `revealed`             | Entries visible, voting may open.        | voting, completed, disputed                         |
| `voting`               | Public voting active.                    | completed, disputed                                 |
| `completed`            | Result finalized.                        | none                                                |
| `cancelled`            | Battle cancelled.                        | none                                                |
| `disputed`             | Admin review needed.                     | completed, cancelled                                |

## Business rules

| Rule                               | Description                                              |
| ---------------------------------- | -------------------------------------------------------- |
| Created from accepted challenge    | Battle should normally originate from `BattleChallenge`. |
| Two participants only in MVP       | Group battles can come later.                            |
| Submission deadline required       | Default MVP: 24 hours after acceptance/start.            |
| Voting deadline required           | Voting window should be explicit.                        |
| Winner only after completion       | Prevent inconsistent result states.                      |
| Result reason required             | Example: public_vote, no_show, admin_decision.           |
| Battle state changes create events | Each important transition should create `BattleEvent`.   |

---

# 5. BattleEntry

## Purpose

Stores submitted content for each participant.

## Moderation statuses

| Status     | Meaning                                 |
| ---------- | --------------------------------------- |
| `pending`  | Awaiting review if moderation required. |
| `approved` | Valid for battle.                       |
| `rejected` | Cannot be used.                         |
| `flagged`  | Needs admin review.                     |

## Business rules

| Rule                                   | Description                                  |
| -------------------------------------- | -------------------------------------------- |
| One entry per participant              | Unique battle + author.                      |
| Author must be participant             | No third-party submissions.                  |
| Existing content must belong to author | Cannot submit someone else’s recipe/article. |
| Content must be approved               | Draft/rejected content cannot be used.       |
| Hidden before reveal                   | Templates/selectors must enforce this.       |
| Late entry tracked                     | Late submission may cause penalty.           |

---

# 6. BattleVote

## Purpose

Stores public voting.

## Business rules

| Rule                         | Description                                              |
| ---------------------------- | -------------------------------------------------------- |
| Authenticated voting in MVP  | Simpler and safer.                                       |
| One vote per user per battle | Unique constraint required.                              |
| No self-voting               | Battle participants cannot vote.                         |
| Vote only after reveal       | No voting on hidden entries.                             |
| Vote only before deadline    | Server-side check required.                              |
| Store hashed metadata        | IP/user-agent/session hash can help abuse review.        |
| Vote can be suspicious       | Suspicious votes may be excluded later by admin/service. |

---

# 7. BattleEvent

## Purpose

Makes the battle “sound across the site”.

## Event types

| Event type           | Public?         | Example message                            |
| -------------------- | --------------- | ------------------------------------------ |
| `challenge_created`  | Optional        | Chef A challenged Chef B.                  |
| `challenge_accepted` | Yes             | Chef B accepted the challenge.             |
| `challenge_refused`  | Optional/public | Chef B refused the challenge.              |
| `challenge_expired`  | Usually no      | Challenge expired.                         |
| `battle_started`     | Yes             | Battle started: Modern Irish Comfort Food. |
| `entry_submitted`    | Optional        | Chef A submitted their entry.              |
| `battle_revealed`    | Yes             | Battle entries are now revealed.           |
| `vote_cast`          | Usually no      | Vote recorded.                             |
| `battle_finished`    | Yes             | Battle finished.                           |
| `chef_defeated`      | Yes             | Chef A defeated Chef B.                    |
| `crown_awarded`      | Yes             | Chef A is now Crown Holder.                |
| `rank_promoted`      | Yes             | Chef A reached Head Chef rank.             |

## Business rules

| Rule                                 | Description                                                 |
| ------------------------------------ | ----------------------------------------------------------- |
| Events are immutable by default      | Prefer creating new correction events over editing history. |
| Public events feed homepage/profile  | Reusable for site-wide activity.                            |
| Event payload stores structured data | Keep message readable and payload machine-friendly.         |
| Avoid spam                           | Not every tiny action should appear site-wide.              |

---

# 8. Rank ladder

| Rank            | Suggested rating/reputation meaning |
| --------------- | ----------------------------------- |
| Kitchen Porter  | New / entry-level participant       |
| Prep Cook       | Some activity                       |
| Commis Chef     | Regular contributor                 |
| Chef de Partie  | Proven battle participant           |
| Sous Chef       | Strong competitor                   |
| Head Chef       | High-status chef                    |
| Executive Chef  | Elite platform chef                 |
| Culinary Master | Top-tier legendary status           |

## Business rules

| Rule                                   | Description                                                      |
| -------------------------------------- | ---------------------------------------------------------------- |
| Rank should not depend only on PvP     | Combine battle rating and culinary reputation where appropriate. |
| Rank promotion should create event     | Promotions are public status moments.                            |
| Rank demotion should be used carefully | Avoid discouraging users too aggressively early on.              |

---

# 9. Rating and reputation

## Battle Rating

Used for PvP strength.

Affected by:

* wins
* losses
* opponent strength
* streaks
* repeated opponent reduction
* refusal penalties if desired

## Culinary Reputation

Used for platform-wide author value.

Affected by:

* approved recipes
* approved articles
* likes
* comments
* consistency
* battle participation
* seasonal events

## Rule

Battle Rating and Culinary Reputation must be separate.

Reason:

A chef can be a strong content creator without being the best PvP fighter, and a PvP fighter should still be encouraged to publish real content.

---

# 10. Crown system

## Crown rules v1

| Rule             | Description                                                      |
| ---------------- | ---------------------------------------------------------------- |
| Crown duration   | 24 hours                                                         |
| Crown trigger    | Winning qualifying battle                                        |
| Crown visibility | Profile, battle page, leaderboard, homepage block                |
| Crown expiry     | Time-based                                                       |
| Crown transfer   | Later winner may replace current crown holder depending on rules |

## Crown event example

```text
👑 Chef Aidan Byrne is now the Reigning Chef for 24 hours.
```

---

# 11. Battle lifecycle

## MVP lifecycle

```text
pending challenge
→ accepted challenge
→ battle created
→ battle active
→ entries submitted
→ entries revealed
→ voting open
→ voting closed
→ result calculated
→ stats updated
→ crown/rank events created
→ battle completed
```

## Refusal lifecycle

```text
pending challenge
→ refused
→ refusal recorded
→ reputation penalty optional
→ public/private event created
```

## Expiry lifecycle

```text
pending challenge
→ no response before expires_at
→ expired
→ ignored count optional
→ event created
```

---

# 12. MVP permissions

| Action                   | Allowed user                                               |
| ------------------------ | ---------------------------------------------------------- |
| Create challenge         | Logged-in eligible author/chef                             |
| Accept challenge         | Opponent only                                              |
| Refuse challenge         | Opponent only                                              |
| Cancel challenge         | Challenger or admin                                        |
| Submit battle entry      | Battle participant only                                    |
| Vote                     | Logged-in non-participant                                  |
| View battle              | Public                                                     |
| View hidden entries      | Participants/admin before reveal, public only after reveal |
| Complete battle manually | Admin/service only                                         |
| Dispute battle           | Admin/moderator                                            |

---

# 13. Anti-abuse rules

| Abuse risk                    | Protection                                       |
| ----------------------------- | ------------------------------------------------ |
| Challenge spam                | Active challenge limits, cooldowns               |
| Harassment                    | Same-pair cooldown, admin blocking               |
| Self-voting                   | Participant vote block                           |
| Duplicate voting              | Unique vote constraint                           |
| Fake accounts                 | Authenticated voting, future trust scoring       |
| Vote brigading                | IP/session metadata, anomaly flags               |
| Farming weak opponents        | Reduced rating gain for repeated weak targets    |
| Content spam                  | Only approved content earns points/moves         |
| Paid domination               | Limits on paid energy, no direct artifact buying |
| Repeated refusal manipulation | Cooldowns and balanced penalty rules             |

---

# 14. Phase map

| Phase | Name                  | Main outcome                                                      |
| ----: | --------------------- | ----------------------------------------------------------------- |
|     0 | Foundation            | App, models, services, tests, architecture                        |
|     1 | MVP Battle Core       | Challenge, battle room, submission, voting, result, rating, crown |
|     2 | Social Visibility     | Homepage feed, profile activity, notifications, battle history    |
|     3 | Energy Economy        | Earned battle moves from recipes/articles/likes/wins              |
|     4 | Combat Engine         | Attack/block/missed hit/partial defence mechanics                 |
|     5 | Artifacts & Cosmetics | Earned artifacts, premium cosmetics, profile prestige             |
|     6 | Seasons & Clans       | Seasonal rankings, tournaments, kitchens/clans, regional leagues  |
|     7 | Sponsorship & Media   | Sponsored battles, recaps, social content, commercial events      |

---

# 15. MVP Definition of Done

The MVP is complete when this works end-to-end:

```text
Chef A challenges Chef B.
Chef B accepts.
Battle Room is created.
Both submit entries.
Entries are hidden until reveal.
Visitors vote.
Battle ends.
Winner is calculated.
Rating updates.
Crown is awarded.
Public event appears on the site.
Profiles show updated battle stats.
Admin can inspect the battle.
Tests pass.
```

---

# 16. Product warning

Do not start Phase 4 combat mechanics before Phase 1 and Phase 2 are stable.

The first real value is not attack/block complexity.

The first real value is:

```text
public challenge + social pressure + status + visibility + return visits
```

That is the retention engine.
