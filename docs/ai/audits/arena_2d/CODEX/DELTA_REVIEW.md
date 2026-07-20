# CODEX Delta Review

## Exact target commit verified

- Worktree: `E:/CulinEire Project/CulinEire/CulinEire/.audit-worktrees/DELTA_CODEX/CODEX`
- Branch: `audit/arena-2d-delta-codex`
- HEAD: `2a28e4b2c3be0e1baad7340e06aa1f020931e025`
- Audited range only: `726e338076462982185e3caa7564cc37977a18c9..2a28e4b2c3be0e1baad7340e06aa1f020931e025`

The worktree was created directly from the target commit. No unchanged file was re-audited and no production file was modified.

## Changed files in owned lane

| File | Delta reviewed | Effect on audit |
|---|---|---|
| `chef_battle/access.py` | Dark-launch visibility now allows every authenticated user with a `RecipeAuthor`; staff/superuser still allowed; anonymous and authenticated users without an author remain hidden | Amends the access-state description, not the frontend rebuild boundary |
| `chef_battle/fraud.py` | Fingerprint comparisons now filter on `HASH_SCHEME_CURRENT` | Strengthens vote-integrity contract |
| `chef_battle/models.py` | Adds hash-scheme constants, `BattleVote.voter_author`, vote/event hash scheme and DB self-vote constraint | Newly reusable integrity enforcement; schema amendment |
| `chef_battle/migrations/0083_vote_self_vote_constraint_and_hash_scheme.py` | Backfills voter authors, labels legacy hashes and creates self-vote constraint | Must be preserved; migration can block on historical self-votes by design |
| `chef_battle/services.py` | Request hashes changed from bare SHA-256 to keyed HMAC-SHA256 | Privacy/integrity contract amendment |
| `chef_battle/views.py` | Vote creation supplies denormalised `voter_author` | Completes DB constraint path; Arena payload unchanged |
| `chef_battle/tests.py` | Adds visibility, DB self-vote, hash-scheme and privacy regression tests | Increases confidence; geometry tests remain but do not change presentation classification |

## Previous audit conclusions still valid

- Backend/domain logic remains the preservation boundary for the 2D rebuild.
- `Battle.status`, deadlines, challenge transitions, submission/reveal, moderation, scoring, crown, gifts and viewer-presence contracts are unchanged.
- Arena page/state payload structure and phase/deadline/metrics contracts are unchanged in this delta.
- Voting and fraud rules remain server-authoritative and must not be duplicated in frontend JavaScript.
- No backend file becomes dead code or a duplicate candidate.
- The minimum safe rebuild remains presentation-only, subject to the existing Arena Master Console renderer dependency.
- No backend business feature becomes genuinely missing.

## Previous audit conclusions requiring amendment

1. Dark-launch access is no longer limited to staff/superuser/bearseeker accounts. At the intended base, every authenticated account with a `RecipeAuthor` may view the Arena without Chef Battle enrollment. Anonymous users and accounts without an author still receive the hidden state while the global feature flag is off.
2. Vote self-protection is stronger than the audited base: it now includes a database `CheckConstraint` through the denormalised `voter_author` field, in addition to fraud gates and model/view validation.
3. Fingerprint privacy and comparison semantics changed: new request hashes use HMAC-SHA256 and carry scheme `v2`; historical values remain labelled `v1`, and fraud comparisons are scheme-scoped.
4. The migration is a preservation risk: existing historical self-vote rows cause an explicit migration stop requiring an owner data decision. This is not evidence of a current defect and was not exercised against production during this analysis.

## Newly discovered reusable functionality

- Database-enforced self-vote protection independent of callers invoking `full_clean()`.
- Explicit voter-author linkage usable for integrity enforcement and audit-safe relations.
- Versioned fingerprint schemes allowing honest coexistence of legacy and keyed hashes.
- HMAC pseudonymisation that retains deterministic comparison without storing reversible bare IP digests.
- Regression tests covering plain-author Arena visibility, no-author denial, direct-save constraint enforcement and hash behaviour.

## Newly discovered risks

- Future UI copy or tests may still describe dark launch as staff-only and incorrectly hide ordinary authors client-side.
- Any vote-writing path that fails to set `voter_author` for a user who has an author weakens the DB self-vote constraint because the field is nullable; the audited `battle_vote` path does set it.
- Migration `0083` intentionally stops if historical self-votes exist; deployment readiness requires a read-only preflight or explicit owner decision if triggered.
- Rotating `SECRET_KEY` changes new HMAC outputs, so fraud comparisons rely on operational key continuity and the single `v2` label does not encode key rotation.
- Scheme-scoped fraud gates no longer compare legacy `v1` rows with new `v2` rows, which is correct cryptographically but creates a limited transition window for device/IP duplicate detection.

## Contract changes

| Contract | Audited base | Intended base | Classification |
|---|---|---|---|
| Dark-launch viewer eligibility | staff/superuser/bearseeker | staff/superuser or any authenticated `RecipeAuthor` | MINOR_AMENDMENT |
| Chef enrollment required to watch | No | Explicitly no | NO_CHANGE, now documented/tested |
| Self-vote enforcement | fraud gate/model validation | fraud gate/model validation plus DB constraint | MINOR_AMENDMENT |
| Vote fingerprint recipe | bare SHA-256 | HMAC-SHA256 keyed by `SECRET_KEY` | MINOR_AMENDMENT |
| Fingerprint comparison | hash value only | hash value plus current scheme | MINOR_AMENDMENT |
| Public Arena payload/actions | Existing contract | No delta change | NO_CHANGE |

## Test evidence

Exact-target commands used isolated audit paths and SQLite; no production database was accessed.

| Command | Result |
|---|---|
| `manage.py check` | PASS: no issues |
| `manage.py makemigrations --check --dry-run` | PASS: no changes detected |
| `ArenaDarkLaunchTests`, `ChefBattleAntiAbuseTests`, `VoteIntegrityConstraintTests`, `RequestHashTests` | PASS: 20/20 in 45.177 seconds |
| `git diff --name-status/stat/log 726e3380..2a28e4b2` | PASS: target delta enumerated |

## Final delta status

**MINOR_AMENDMENT**

The intended baseline strengthens access documentation/tests, vote integrity and fingerprint privacy. It does not invalidate the original audit's backend preservation boundary, frontend-only reconstruction recommendation, dead-code conclusions or implementation stop. The master synthesis needs a narrow access/integrity amendment and must record that it was originally based on `726e3380`, not the intended target.
