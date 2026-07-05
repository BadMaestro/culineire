# Vote integrity privacy report

## Vote integrity evidence

`VoteIntegrityEvent` is a private security record for a rejected voting attempt.
It is deliberately separate from `BattleVote` and therefore cannot affect public
totals, percentages, ties, completion, or winner calculation.

Stored fields:

- battle identifier;
- primary gate code and the set of failed gate codes;
- whether the request was authenticated (boolean only);
- SHA-256 hashes of IP address, user-agent and an existing session key;
- timestamp.

Not stored:

- raw IP address, raw user-agent or raw session key;
- user/account foreign key, username or email;
- free-text internal gate reason;
- requested participant choice.

Access:

- no public endpoint serialises this model;
- Django admin registration is read-only and requires staff admin access;
- P06 console analytics may expose only aggregate counts and gate codes to
  authorised console operators, never request hashes or voter identity.

Retention:

Each record receives an indexed expiry timestamp 90 days after creation. The
`purge_vote_integrity_events` management command deletes expired rows and offers
`--dry-run` for operational verification. Production scheduling of this command
is a deployment responsibility and must be monitored like the existing stale
battle/reward expiry jobs.

## P06 console analytics delivery (2026-07-05)

All P06 analytics are served exclusively through the console gate
(`master_state`). Public arena JSON is test-verified free of analytics keys
(`votes_per_hour`, `enforcement`, `suspicious_queue`, `challenger_pct`).

- Suspicious queue exposes only vote id, target chef slug, timestamp — voter
  usernames test-asserted absent from the full payload; `"ip_hash"` /
  `"user_agent_hash"` JSON keys test-asserted absent (values never leave the DB).
- Rejected attempts shown only as aggregates grouped by gate code (total + 24h).
- Community support aggregated per recipient chef; individual supporter
  identities deliberately not shown.
- `is_suspicious` presented as "flagged for review" (manual moderator mark);
  no automated risk score exists and none is displayed.
- Zero votes produce NULL percentages, never an invented 50/50.
- Truthful time semantics: votes-per-hour bucketing was silently in site TZ
  (Europe/Dublin) while labelled UTC — `TruncHour(tzinfo=UTC)` forced, every
  bucket test-asserted to carry `+00:00`.

Verification: `ArenaMasterVotingAnalyticsTests` 9/9; full `chef_battle` suite
green with default flags (anti-abuse and auto-completion suites included);
public voting flow and arena popup untouched.
