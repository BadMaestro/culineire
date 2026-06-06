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
