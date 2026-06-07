## Sponsors Compliance Summary

Completed phases:

- Phase 1: sponsor declaration before Stripe, paid pending compliance review, manual compliance clear before approval, approve/publish flow and sponsor moderation attention badges.
- Phase 2: official EU/UN sanctions source ingestion, source snapshots, EU RSS discovery, manual EU file fallback and staff source freshness visibility.
- Phase 3: internal possible sanctions match workflow, staff review decisions, audit logging and approval blocking for unresolved or blocked matches.
- Phase 4: enforcement around blocked compliance, refund required, manual refund completion and safe sponsor cell state rules.
- Phase 5: legal-facing wording, applicant/staff UI clarity, notification wording and documentation polish.
- Phase 6: Stripe live readiness checklist, mode/key safety guards, owner/accountant review checklist and rollback/cleanup documentation.

Current sponsor flow:

```text
application + declarations -> Stripe Checkout -> paid_pending_compliance_review
-> sanctions screening / staff compliance review
-> manual clear -> paid_pending_approval -> approve and publish -> approved/active
```

Payment reserves the selected sponsor spot while Bearcave Limited completes staff review. It does not guarantee approval, publication or activation. Sponsor names, logos, avatars and website/profile links are not public until approval and publication.

If an application cannot proceed, staff can reject and mark refund required. Refund tracking is manual: CulinEire records the operational status and releases the sponsor cell only after staff records refund completion. The application does not call the Stripe refund API.

Public data safety rules:

- Do not expose sanctions match details publicly.
- Do not expose sanctions source URLs, tokenized EU URLs or raw sanctions payloads publicly.
- Do not expose staff notes, audit logs or Stripe payment identifiers publicly.
- Telegram sponsor announcements are sent only after Approve and publish.

Still out of scope: automatic Stripe refunds, full AML/KYC, beneficial ownership collection, scheduled re-screening, live Stripe switch and legal/applicant workflow beyond the current sponsor declarations and review process.

## Sponsors Phase 6: Stripe Live Readiness

Phase 6 does not switch Stripe to live mode. It adds readiness checks and documentation for a future live switch.

Runtime safeguards:

- `STRIPE_PRICE_MODE` must be `test` or `live`.
- `sk_live_` secret keys are rejected in test mode.
- `sk_test_` secret keys are rejected in live mode.
- Publishable key mode mismatches are rejected when a publishable key is configured.
- Stripe webhook verification still requires `STRIPE_WEBHOOK_SECRET`.

The current checkout implementation uses server-side `price_data` from `SponsorCell.price_net_cents`. It does not use separate Stripe Price IDs. If Stripe Price IDs are introduced later, test and live IDs must be separated and validated before live use.

Readiness documentation:

- `docs/sponsor_stripe_live_readiness.md` contains the owner/accountant/developer checklist.
- `docs/stripe_sponsors_checklist.md` remains the manual smoke-test checklist and now references the Phase 6 live-readiness document.

Items requiring owner/accountant/Stripe review before live mode:

- Stripe account activation.
- Live Automatic Tax/VAT setup.
- VAT rate handling and customer tax ID behaviour.
- Production email delivery.
- Live webhook endpoint and signing secret.
- Final sandbox cleanup and database backup.

Phase 6 still leaves out automatic Stripe refunds, full AML/KYC, beneficial ownership collection, scheduled re-screening, real live payments and the actual live Stripe switch.

## Sponsors Compliance Phase 2

Phase 2 imports official EU and UN sanctions source XML files and tracks source freshness for staff review.

It does not perform sponsor matching, AML/KYC checks, or automatic approval decisions. Sponsor matching and possible-match workflow are Phase 3 work.

After deployment, run:

```bash
DJANGO_ENV_FILE=/srv/culineire/shared/.env python manage.py update_sanctions_sources --source all
```

If the official EU Webgate endpoints return HTTP 403 from the server, manually download the official EU Financial Sanctions Files XML or CSV from the EU FSF/data.europa.eu page, upload the file to the server, and import it into the same Phase 2 snapshot tables:

```bash
DJANGO_ENV_FILE=/srv/culineire/shared/.env python manage.py update_sanctions_sources --source eu --from-file /srv/culineire/shared/imports/eu-fsf.xml
```

CSV is also supported:

```bash
DJANGO_ENV_FILE=/srv/culineire/shared/.env python manage.py update_sanctions_sources --source eu --from-file /srv/culineire/shared/imports/eu-fsf.csv
```

Use only officially downloaded EU Financial Sanctions Files. Do not use third-party sanctions aggregators for this import.

## Sponsors Compliance Phase 3

Phase 3 adds internal sanctions screening for paid sponsor applications. It compares available sponsor/application names against the imported official EU FSF and UN sanctions subjects and records explainable possible sanctions matches for staff review.

This is not full AML/KYC and does not automatically reject, approve, refund or publish a sponsor. It is an internal manual compliance review aid. Sponsor applications with unresolved possible sanctions matches, or a blocked compliance decision, cannot be approved and published until staff review is completed.

Run screening for one application:

```bash
DJANGO_ENV_FILE=/srv/culineire/shared/.env python manage.py screen_sponsor_application --application-id 123
```

Useful options:

```bash
--dry-run
--force
--verbose
```

Staff can review possible matches from the sponsor moderation detail page and mark each match as false positive, manually cleared or blocked for compliance. Each decision requires a staff note and is written to the sponsor audit log.

Left out for later phases: full fuzzy matching libraries, external API calls, automatic legal rejection, refund automation, public match display, beneficial ownership collection, full AML/KYC and scheduled rescreening of all active sponsors.

## Sponsors Compliance Phase 4

Phase 4 hardens the staff enforcement path after a sponsor has paid but cannot yet be approved.

Approval and publication remain blocked while sanctions compliance is unresolved or blocked. This includes unresolved possible matches, blocked match decisions and blocked compliance checks. Staff see the explicit message: "This sponsor application cannot be approved while sanctions compliance review is unresolved or blocked."

Staff next steps for a paid application on compliance hold are manual:

- request changes or more information, keeping the paid cell reserved
- mark a possible match false positive or manually cleared with a required staff note
- block for compliance with a required staff note
- reject and mark refund required with a required staff note
- mark refund completed manually with a required staff note

Refund tracking is manual in this phase. CulinEire records "Refund required" and "Refund completed manually", updates payment/application status, writes audit log entries and releases the sponsor cell only after staff mark the refund completed. Phase 4 does not call the Stripe refund API.

Sponsor cell rules:

- payment pending and paid compliance review keep the selected cell reserved/unavailable
- changes requested after payment keeps the selected cell reserved
- blocked compliance without a terminal decision keeps the selected cell reserved
- approved/published sets the cell active
- refund required keeps the cell reserved until refund completion
- refund completed releases the cell back to available and clears public sponsor fields
- unpaid rejection releases the cell back to available
- expiry keeps the existing expired-cell design
- unpublish keeps the existing unavailable-cell design and removes the public active benefit

The sponsor moderation attention badge includes paid compliance review, paid approval, changes requested, refund required, unresolved possible sanctions matches and blocked compliance applications that still need staff action.

Cleanup commands continue to protect paid/refund/compliance states. Deleting a safe sandbox sponsor application cascades its SponsorSanctionsMatch rows, but official SanctionsSourceSnapshot and SanctionsSubject records are not deleted by sponsor application cleanup.

Left out for later phases: automatic Stripe refunds, applicant-facing legal copy overhaul, full AML/KYC, beneficial ownership collection, scheduled re-screening and live Stripe switch.
