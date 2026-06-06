## Sponsors Compliance Phase 2

Phase 2 imports official EU and UN sanctions source XML files and tracks source freshness for staff review.

It does not perform sponsor matching, AML/KYC checks, or automatic approval decisions. Sponsor matching and possible-match workflow are Phase 3 work.

After deployment, run:

```bash
DJANGO_ENV_FILE=/srv/culineire/shared/.env python manage.py update_sanctions_sources --source all
```
