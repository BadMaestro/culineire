# Stripe Sponsors Manual Test Checklist

## Test Mode

1. Set `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_MODE=test`, and `SITE_BASE_URL`.
2. In Stripe, enable Automatic Tax and confirm Bearcave Limited VAT details are configured.
3. Open `/sponsors/` and confirm prices display as net price plus VAT.
4. Choose an available non-centre sponsor cell.
5. Submit sponsor name, contact name, email, optional website/profile URL, logo or avatar, and all required confirmations.
6. Drag and resize the uploaded image in the exact cell preview, then continue to checkout.
7. Confirm Stripe Checkout opens with one annual sponsor line item, EUR currency, exclusive tax behaviour, billing address collection, tax ID collection, and automatic tax.
8. Complete a Stripe test card payment.
9. Confirm `/sponsors/checkout/success/` states that payment was received, the spot is reserved, sponsorship is not active yet, and compliance/staff review is required before publication.
10. Confirm the Stripe webhook sets the application to `paid_pending_compliance_review`, keeps the cell reserved, and does not publish the image.
11. In sponsor moderation, complete sanctions/compliance review. Confirm unresolved or blocked possible sanctions matches prevent approval.
12. After manual compliance clear, approve the application and confirm the logo/avatar appears publicly with the selected placement.
13. Confirm `published_at` is set to approval/publication time and `expires_at` matches the product term.
14. Repeat with a second paid application and reject it with a staff note; confirm it becomes `refund_required`, the cell remains reserved, and no image is published.
15. Process the refund manually in Stripe, then mark refund completed in CulinEire with a staff note and confirm the cell is released.
16. Start checkout and cancel before payment; confirm the application is cancelled and the cell is available again.
17. Trigger `checkout.session.expired`; confirm unpaid cells are released.

## Live Deployment Checklist

1. Confirm production `SITE_BASE_URL=https://culineire.ie`.
2. Confirm live Stripe keys and webhook secret are loaded from environment variables only.
3. Confirm Stripe webhook endpoint is configured as `/sponsors/stripe/webhook/`.
4. Confirm no secret key or webhook secret appears in templates, logs, admin display, or source code.
5. Confirm Automatic Tax is enabled in Stripe live mode.
6. Confirm Bearcave Limited VAT number is configured and visible in the internal roadmap checks.
7. Run Django migrations.
8. Run the sponsor test suite.
9. Complete one low-value live test if appropriate, then refund it manually through Stripe and record manual refund completion in CulinEire.
10. Confirm the sponsor roadmap is visible only to superusers or GreenBear owner access.
11. Confirm no public page exposes sanctions match details, staff notes, audit logs, tokenized EU URLs or Stripe payment identifiers.
