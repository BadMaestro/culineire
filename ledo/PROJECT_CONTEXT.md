# LEDO Drive project context

## Product

LEDO Drive is a focused airport-transfer booking-request site for the two
directions between Kongsberg and Oslo Airport Gardermoen. The primary language
is Norwegian Bokmal. The primary conversion is a successfully submitted
booking request.

## MVP decision

The current flow is a booking request, not instant guaranteed booking. An
operator confirms availability after submission. There is no online payment in
this version. Prices are configured in the admin, calculated on the server and
snapshotted on the booking.

## Confirmed scope

- server-rendered Django pages, semantic HTML, CSS and small vanilla JavaScript;
- landing page, price display, booking request and confirmation;
- operator queue through Django Admin;
- route, fare, booking, separate customer contact and audit event records;
- Europe/Oslo journey semantics;
- private preview on the existing CulinEire server.

## Non-goals

- customer accounts;
- live vehicle tracking;
- automatic dispatch;
- dynamic pricing;
- payment collection;
- maps, analytics, advertising or marketing cookies;
- driver or multi-vehicle scheduling.

## Facts still requiring owner approval

Legal entity, organisation number, transport licence, official address,
telephone, email, final fares, VAT and toll treatment, waiting/no-show rules,
cancellation/refund policy, vehicle capacity, child-seat availability, service
hours, minimum lead time, payment method and retention period remain unverified.
The UI must not present any of them as facts until approved.
