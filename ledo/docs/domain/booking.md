# Booking request domain

## Creation

A booking request can be created only for an active route with a current active
fare. The server ignores any amount or currency supplied by the browser. It
selects the current fare, calculates one-way or return pricing, and stores an
immutable snapshot with the request.

Pickup and return values are interpreted in `Europe/Oslo`. Pickup must be in the
future and return must follow pickup. A return request is accepted only when the
fare has a return price.

The request stores travel details separately from `CustomerContact`. Every
successful creation writes `booking.requested` to `AuditEvent`.

## Idempotency

Every rendered form receives a random UUID. `Booking.idempotency_key` has a
unique database constraint. Replaying the same submission returns the original
booking and cannot create a second contact or audit event.

## Statuses

The initial status is `PENDING_CONFIRMATION`.

Allowed transitions:

- `PENDING_CONFIRMATION` to `CONFIRMED`, `CANCELLED_BY_CUSTOMER` or
  `CANCELLED_BY_OPERATOR`;
- `CONFIRMED` to `COMPLETED`, `CANCELLED_BY_CUSTOMER`,
  `CANCELLED_BY_OPERATOR` or `NO_SHOW`.

All transitions go through `transition_booking()`, lock the row, reject invalid
transitions and write `booking.status_changed` with old and new values.

## Privacy and access

The public confirmation uses a UUID and is visible only to the browser session
that created it; staff may inspect it during preview. CSV export excludes name,
email, phone, notes and flight number. Contact retention remains an owner/legal
decision and therefore is not automated yet.
