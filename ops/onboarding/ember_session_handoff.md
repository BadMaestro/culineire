# Ember session handoff - 2026-08-15

This is a short local-work handoff, not a source of dynamic truth. On restart,
read the mandatory cold-start documents from `origin/main`, then reconcile every
hash below.

## Exact state at handoff

- Worktree: `E:\CulinEire Project\CulinEire\login-csrf-recovery`
- Branch: `codex/login-csrf-recovery`
- Production: `v2.5.1034`, `eee3afef820a13d47ec51e2ed916598fec1ee248`
- Local product tip before this handoff commit: `4c2bc842e439b89b8a58096a81082b0c29d29bf1`
- Remote branch and `origin/main`: `eee3afef`
- Deploy lock: free
- Local PostgreSQL keepalive: stopped
- Tests on Linode: none

## Local commits not delivered

1. `39bcad61 docs(arena): correct Stage 1 ingredient combat rule`
   - T11 now records the Owner's actual mechanic.
   - Both chefs secretly lock two ingredients before Stage 1.
   - Only the Stage 1 winner fires three shots; the loser only defends.
   - No sequential loser-lock/winner-shot 48-hour windows.

2. `4c2bc842 feat(arena): add Owner account controls to chef cards`
   - Owner-only Arena card menu: Mute, timed full-site Block, Delete Account.
   - Mute rejects Arena chat until the deadline.
   - Block deletes active sessions and the auth backend rejects login until expiry.
   - Delete requires the server-side checkbox, deletes User/personal profile data,
     and keeps mandatory battle/money history under an anonymised `Deleted Chef`.
   - Immutable `LedgerEvent.ADMIN_NOTE` records every action.
   - GreenBear cannot target itself; staff/superuser is not a substitute for OWNER_SLUG.
   - Additive migration: `chef_battle/0096_owner_arena_account_controls.py`.

## Evidence

- New Owner controls: 4/4 PostgreSQL tests PASS.
- Adjacent Arena/access/chat/login/image set: 33/33 PASS, PostgreSQL, parallel 8.
- `manage.py check`: clean.
- `makemigrations --check --dry-run`: no changes.
- `node --check static/js/arena_render.js`: clean.
- `git diff --check`: clean.

## Next safe action

Reconcile/fetch first. If these commits are still absent from `origin/main`,
review the two commits, run the Arena-only PostgreSQL acceptance manifest, then
prepare a new Ember release number by adding three to 1034 (`v2.5.1037`). Read
AGENTS.md sections 8 and 17 immediately before any deploy. Never test on Linode.

The separate GreenBear game contract is not implemented by T18: GreenBear may
appear on Arena and join clans/alliances for cosmetics plus a clan-reputation
blessing, but cannot be challenged, fight, or contribute to any competitive
ranking or aggregate. It needs its own card and Owner-set reputation amount.
