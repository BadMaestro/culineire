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
