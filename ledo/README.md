# LEDO Drive MVP

LEDO is an isolated Django application hosted by the existing CulinEire process.
It uses its own URL namespace, templates, static files, models, migrations and
admin screens. It does not import CulinEire product models or templates.

## Preview

- URL: `/ledo/`
- Health check: `/ledo/health/`
- Feature flag: `LEDO_ENABLED=True`
- Private preview gate: `LEDO_PREVIEW_STAFF_ONLY=True`
- Search indexing: disabled while the application remains a preview

Both flags have safe defaults: deploying the code alone does not expose LEDO,
and enabling LEDO still limits the page to authenticated staff. The public
release later sets `LEDO_PREVIEW_STAFF_ONLY=False` only after business, legal,
content and pricing approval.

## Implemented MVP slice

- responsive Norwegian Bokmal landing page;
- active routes and date-versioned fares managed in Django Admin;
- booking requests with a server-authoritative price snapshot;
- one-way and return journeys in the Europe/Oslo timezone;
- idempotency key, unique database constraint, honeypot and session rate limit;
- customer contact stored separately from the journey record;
- operator-controlled status transitions and immutable audit events;
- CSV export without contact fields;
- private confirmation page accessible only to the originating browser session
  or staff.

No payment, SMS, analytics, maps or marketing trackers are present. Those are
deliberately deferred until the corresponding business and privacy decisions
are approved.

## Local verification

Set a development secret and run:

```powershell
$env:DJANGO_SECRET_KEY='local-only-key'
$env:DJANGO_ENV='development'
$env:LEDO_ENABLED='True'
$env:LEDO_PREVIEW_STAFF_ONLY='False'
python manage.py migrate
python manage.py test ledo
python manage.py runserver
```

The application intentionally seeds no production route or price. Create and
approve `Route` and `Fare` rows in Django Admin before testing the form.
