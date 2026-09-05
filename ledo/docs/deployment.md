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
