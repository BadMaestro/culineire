# Sponsor Stripe Live Readiness Checklist

This checklist is for staff/developer review before enabling real sponsor payments. It is not the live switch and does not authorise live payments by itself.

## Current Readiness State

Status: ready for project owner, accountant and Stripe account review before live mode.

Not complete until the project owner confirms:

- Stripe account activation and live payment capability.
- Live Automatic Tax and VAT configuration.
- Live webhook endpoint and signing secret.
- Live keys loaded only through production environment variables.
- Final sandbox data cleanup and database backup.

## Environment Separation

Required before live mode:

- `STRIPE_PRICE_MODE=live`.
- `STRIPE_SECRET_KEY` starts with `sk_live_`.
- `STRIPE_PUBLISHABLE_KEY` starts with `pk_live_`.
- `STRIPE_WEBHOOK_SECRET` is configured from the live webhook endpoint.
- Test keys must not be used in live mode.
- Live keys must not be used in test mode.
- Stripe secrets must never be committed to git, templates, logs or admin display.

Current implementation uses server-side `price_data` built from `SponsorCell.price_net_cents`; it does not use separate Stripe Price IDs. If Stripe Price IDs are introduced later, test and live IDs must be separated and validated before live use.

## Checkout Readiness

Confirmed by code/tests:

- Checkout is created only after sponsor declarations are accepted.
- The frontend does not control price.
- Product type, cell and net price are resolved server-side from `SponsorCell`.
- Reserved/unavailable cells cannot be repurchased.
- Success and cancel URLs are built from `SITE_BASE_URL` or the current request host.
- Stripe Checkout uses one-off `mode=payment`.
- Stripe Automatic Tax is enabled in checkout request.
- Payment does not publish a sponsor.
- Payment moves the application to `paid_pending_compliance_review`.

Manual review before live:

- Confirm `SITE_BASE_URL=https://culineire.ie`.
- Confirm the live checkout page shows EUR, exclusive tax behaviour, billing address collection, tax ID collection and Automatic Tax.
- Requires accountant/Stripe Tax review before live mode: VAT setup, VAT rate handling, customer tax ID behaviour and Irish/EU VAT wording.

## Webhook Readiness

Confirmed by code/tests:

- Stripe webhook signature verification is mandatory.
- Missing webhook secret fails safely.
- Duplicate event IDs are idempotent through `ProcessedStripeEvent`.
- Webhook cannot publish a sponsor.
- Webhook cannot bypass compliance review.
- Payment success, failure, checkout expiry, full refund and partial refund are handled by state-machine tests.
- Webhook error responses do not expose Stripe secrets.

Manual review before live:

- Configure the live Stripe webhook endpoint:
  `https://culineire.ie/sponsors/stripe/webhook/`
- Subscribe only to required sponsor payment events.
- Copy the live signing secret into production environment variables.
- Send one controlled Stripe test event in the live dashboard only when authorised.

## Email Readiness

Current sponsor emails:

- Staff/admin payment received email: tells staff the application is pending compliance review and approval.
- Applicant changes requested email: says publication has not started and no public announcement is sent unless approved and published.

Manual review before live:

- Confirm production email backend credentials.
- Confirm `SPONSOR_ADMIN_EMAIL`.
- Confirm applicant-facing support route for changes/refunds.
- No email should expose sanctions match details, staff notes or Stripe secret data.

## Telegram Readiness

Confirmed by tests/workflow:

- No Telegram announcement on payment.
- No Telegram announcement on compliance clear.
- No Telegram announcement on request changes.
- No Telegram announcement on `refund_required` or `refunded`.
- Telegram sponsor announcement is sent only after Approve and publish.
- Duplicate sponsor approval announcements are deduplicated by `SocialPostLog`.

## Final Test-Mode Cleanup

Do not run cleanup automatically. Before live switch, project owner must decide what test data to remove.

Recommended cleanup review:

- Remove sandbox sponsor applications where safe.
- Remove sandbox payments and processed Stripe events only through the sandbox cleanup command in confirmed test mode.
- Remove sandbox audit logs if appropriate.
- Remove sandbox sanctions matches attached to deleted sandbox applications.
- Release test sponsor cells.
- Keep official `SanctionsSourceSnapshot` and `SanctionsSubject` data.
- Keep Deployment Journal entries.
- Keep production code and migrations.

## Backup And Rollback

Before live switch:

- Take a database backup.
- Record current deployed commit hash.
- Record migration state with `python manage.py showmigrations sponsors`.
- Run `python manage.py check`.
- Run `python manage.py collectstatic --noinput`.
- Confirm Unit restart command works.

Rollback strategy:

- Revert to the previous known-good commit with a normal git checkout/pull strategy approved by the project owner.
- Run migrations only if rollback migration impact is understood.
- Restart Unit.
- Temporarily disable sponsor purchases by removing Stripe keys or setting unavailable cells if needed.
- Keep webhook endpoint disabled in Stripe if live purchase flow must be paused.

## Manual Live Switch Checklist

Do not execute until authorised by the project owner.

- Confirm Stripe account is fully activated.
- Confirm live Automatic Tax/VAT setup with accountant/Stripe review.
- Set production `STRIPE_PRICE_MODE=live`.
- Add live publishable key.
- Add live secret key.
- Add live webhook secret.
- Configure live webhook endpoint.
- Confirm `SITE_BASE_URL=https://culineire.ie`.
- Run `python manage.py check`.
- Run sponsor, newsfeed, legal and recipes test suites in the release branch before deployment.
- Deploy code and collect static files.
- Restart Unit.
- Create one controlled low-risk live sponsor payment only when authorised.
- Verify application enters `paid_pending_compliance_review`.
- Verify no public sponsor listing or Telegram announcement is created before approval.
- Manually clear compliance, approve and publish only if the owner authorises the live smoke test.
- If refund testing is required, process the refund manually in Stripe and record refund completion in CulinEire.

## Not Included In Phase 6

- No live Stripe switch.
- No real payments.
- No automatic Stripe refunds.
- No full AML/KYC.
- No beneficial ownership collection.
- No scheduled re-screening.
- No change to sanctions source ingestion or matching logic.
