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
  gates: ["LEDO PostgreSQL suite and image-weight guard", "migration drift", "diff --check"]
  version_bumped: true
  collectstatic_run: "required by standard deployment"
  rollback_command: "git revert <language-release-commit>; deploy via main using /srv/culineire/scripts/deploy.sh"
  screen_change_in_one_line: "NO / EN / LT / RU switches the LEDO interface language."
```
