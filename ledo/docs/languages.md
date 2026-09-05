# LEDO languages

Supported locales: Norwegian Bokmål (`nb`, shown as NO), English (`en`),
Lithuanian (`lt`) and Russian (`ru`). The language selector is in the header
on desktop and mobile. The initial language is Norwegian.

`?lang=ru` (and the other supported codes) selects the language. A first-party,
HttpOnly, SameSite=Lax cookie scoped to `/ledo/` remembers it for one year.
Only allowed codes are accepted. Invalid codes fall back to Norwegian.
The host's `django_language` cookie and language settings are never modified.
Request-local Django translation overrides also localize built-in form errors
and are restored when the LEDO view returns. Responses are private/no-store.

`ledo/i18n.py` holds the source-backed UI catalog; `ledo_i18n` template tags
and lazy Python translations share it. Keep all four entries for every source.
JavaScript receives translated quote messages through escaped `json_script`.
Route names are operator-managed proper names; monetary values and persisted
booking data are not rewritten when the visitor changes language.

Scope: landing page, navigation, form, validation, quote, FAQ, confirmation
and customer-facing statuses. The shared CulinEire login and Django Admin
remain host application pages; this change does not translate them.

## Release 2.5.1804 gate

Base verified on origin/main and server: `f4e6977c1311d7eb15269a3bf2da285bdedf475b`.
Production previously had no language selector/catalog. No schema change,
public-access change, prices, payments or real-user account actions.
Rollback: revert the language release commit through main and run
`/srv/culineire/scripts/deploy.sh`; no migration rollback or data deletion.
The existing LEDO feature-flag rollback remains available for urgent isolation.

```yaml
pre_deploy_reread:
  constitution_version: "2.12.0"
  sections_reread: ["8", "17"]
  rules_that_apply_here: ["single deploy lock", "current main", "PostgreSQL tests", "no real-user impersonation", "collectstatic", "read index"]
  signed_as: "Bolt"
  index_read: true
  files_in_commit: 15
  base_verified: "f4e6977c1311d7eb15269a3bf2da285bdedf475b"
  already_exists_checked: true
  gates: ["28 PostgreSQL tests PASS including image-weight guard", "migration drift PASS", "diff --check PASS"]
  version_bumped: true
  collectstatic_run: true
  rollback_command: "git revert 4a28d7bf; deploy the resulting reviewed commit"
  screen_change_in_one_line: "NO / EN / LT / RU switches the LEDO interface language."
```

## Verified production result

Release `4a28d7bf2af9a5b523b866366f4c77db2cd3f19d` deployed on
2026-09-05 with an exact-commit, fast-forward-only script. The script required
the documented base and rejected any files outside LEDO, the release journal
and footer version. It did not pull an unconstrained shared main branch.
Two static files copied; 183 post-processed. No migrations needed.
Production template rendering, four selector links and scoped Secure cookies
passed for nb/en/lt/ru. LEDO health, CulinEire home and recipes checks passed.
No real accounts were used and no production bookings were created.
Authenticated browser appearance has not been inspected by the agent.

## Flag selector - 2.5.1807

Local SVG flags now accompany NO/EN/LT/RU, avoiding platform-dependent emoji
rendering. Images are decorative; accessible language names, active selection,
URLs and cookies remain unchanged. Four SVG files total less than 2 KB.

```yaml
pre_deploy_reread:
  constitution_version: "2.12.0"
  sections_reread: ["8", "17"]
  rules_that_apply_here: ["single deploy lock", "read index", "current main", "PostgreSQL tests", "collectstatic", "no real-user login"]
  signed_as: "Bolt"
  index_read: true
  files_in_commit: 11
  base_verified: "41dd0d96be71f407ffe28c521454a35bbc26280b"
  server_base: "4a28d7bf2af9a5b523b866366f4c77db2cd3f19d"
  already_exists_checked: true
  gates: ["LEDO PostgreSQL tests and image weight", "diff --check"]
  version_bumped: true
  collectstatic_run: "required by pinned deployment"
  rollback_command: "git revert the flag-selector release commit and deploy that reviewed commit"
  screen_change_in_one_line: "Four flag icons next to the language codes in LEDO."
```
