# LEDO production preview - v2.5.1777

## Scope

Owner requested deployment to the existing CulinEire server. Preview URL:
https://www.culineire.ie/ledo/ . Existing staff authentication is required.
No customer ordering or payment launch is implied by this preview release.

## Release gate

1. Scope: the new `ledo/` app, settings/URL wiring, environment example,
   footer version and release journal. No unrelated application changes.
2. Base: `0eed11c2efbeec00b32abf90a242a32c403aade7`, verified deployed and on main.
3. Existing production tree contains no `ledo/`; this is a new isolated app.
4. Focused PostgreSQL tests and image-weight guard run with `--parallel 8`;
   migration drift and `git diff --check` must pass before shipping.
5. Version: 2.5.1777, next Bolt slot after 1774.
6. Standard server deployment runs migrate, collectstatic and Unit restart.
7. Safe rollback: `/srv/culineire/venv/bin/python /tmp/ledo-preview-flags.py rollback`
   followed by `sudo /bin/systemctl restart unit`. This hides LEDO without
   deleting its tables or disturbing existing CulinEire code and data.
8. Visible change: standalone Norwegian LEDO landing page, supplied shield logo,
   route overview, request workflow and FAQ. No unapproved prices are seeded.

## Verification

After deployment check the release hash, main CulinEire pages, LEDO health,
anonymous access restriction and a read-only staff-view render. Do not create
fake production bookings, accounts or fares. Do not impersonate a real user.

## Remaining product work

Four complete locales (nb/en/lt/ru), source-document content integration,
verified fleet/rate data and business/legal approvals remain open.
Local supplied files have been preserved under `E:\LEDO DRIVE\LEDO Project`,
with planning, content, fleet, pricing, reference website and brand stages.
Original files are untouched; copied documents/images passed SHA-256 checks.

## Production evidence - 2026-09-05

Release commit: `29a2e7e74f793eba1e20f60938683254087c796a`.
Standard deploy completed at 06:41:06 UTC; `ledo.0001_initial` applied,
3 static files copied, 173 post-processed, both CulinEire health checks passed.
Private preview flags enabled with an environment backup outside the repo.
Production template and staff gate checked independently, without real-user
impersonation. No production bookings or fares exist. Browser verification
reached the sign-in page with `/ledo/` as return target; authenticated browser
review is for the owner, not claimed as completed by the agent.

```yaml
pre_deploy_reread:
  constitution_version: "2.12.0"
  sections_reread: ["8", "17"]
  rules_that_apply_here: ["single deploy lock", "current main", "PostgreSQL tests", "no real-user impersonation", "collectstatic", "reversible feature flag"]
  signed_as: "Bolt"
  index_read: true
  files_in_commit: 3
  release_diff_files: 27
  base_verified: "0eed11c2efbeec00b32abf90a242a32c403aade7"
  already_exists_checked: true
  gates: ["22 PostgreSQL tests PASS --parallel 8 including image weight", "migration drift PASS", "diff --check PASS"]
  version_bumped: true
  collectstatic_run: true
  rollback_command: "/srv/culineire/venv/bin/python /tmp/ledo-preview-flags.py rollback && sudo /bin/systemctl restart unit"
  screen_change_in_one_line: "Staff can view the separate Norwegian LEDO landing page with the supplied logo."
```
