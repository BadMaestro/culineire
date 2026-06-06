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
