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
